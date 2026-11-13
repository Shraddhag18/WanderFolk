"""The web API, end to end, with offline stores in a temp folder (no keys or internet needed)."""
import os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Empty values (not missing ones) so load_dotenv() in server.py can't fill them from .env.
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MEM0_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CREATE_CODE"):
    os.environ[key] = ""

from fastapi.testclient import TestClient

import server
from memory_store import LocalStore, TripStore


class Api(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        server.store, server.trips_db = LocalStore(tmp / "mem.json"), TripStore(tmp / "trips.json")
        server._mem_cache.clear()
        self.c = TestClient(server.app)
        r = self.c.post("/api/trips", json={"name": "Tahoe weekend", "origin": "San Francisco", "days": 2,
                                            "members": "Priya, Arjun\nMaya, priya"})
        self.assertEqual(r.status_code, 200, r.text)
        self.id = r.json()["id"]

    def view(self, me=None):
        return self.c.get(f"/api/trips/{self.id}", params={"me": me} if me else {}).json()

    def test_create_validates_and_dedupes_people(self):
        self.assertEqual(self.view()["trip"]["members"], ["Priya", "Arjun", "Maya"])
        self.assertNotIn("crew", self.view()["trip"])
        self.assertEqual(self.c.post("/api/trips", json={"name": "", "members": "A"}).status_code, 400)
        self.assertEqual(self.c.post("/api/trips", json={"name": "x", "members": ""}).status_code, 400)
        self.assertEqual(self.c.post("/api/trips", json={"name": "x", "members": ",".join(map(str, range(13)))}).status_code, 400)
        self.assertEqual(self.c.get("/api/trips/nope").status_code, 404)

    def test_lookup_accepts_code_or_link(self):
        self.assertEqual(self.c.get("/api/lookup", params={"link": self.id}).json()["id"], self.id)
        self.assertEqual(self.c.get("/api/lookup", params={"link": f"https://x.app/?trip={self.id}"}).json()["id"], self.id)
        self.assertEqual(self.c.get("/api/lookup", params={"link": "junk"}).status_code, 404)

    def test_private_notes_never_reach_other_people(self):
        r = self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Maya", "private": True,
                                                            "answers": {"travel": "Budget about $100 a day"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Arjun", "answers": {"diet": "Vegetarian", "place": ""}})
        as_priya = self.c.get(f"/api/trips/{self.id}", params={"me": "Priya"}).text
        self.assertNotIn("$100", as_priya)
        self.assertIn("Vegetarian", as_priya)
        as_maya = self.view("Maya")
        self.assertIn("Budget about $100 a day", [m["text"] for m in as_maya["memories"]])
        self.assertEqual(self.view("Priya")["waiting_on"], ["Priya"])
        # someone else can't delete it; the owner can
        mid = next(m["id"] for m in as_maya["memories"] if m["private"])
        self.assertEqual(self.c.delete(f"/api/trips/{self.id}/memories/{mid}", params={"me": "Priya"}).status_code, 403)
        self.assertEqual(self.c.delete(f"/api/trips/{self.id}/memories/{mid}", params={"me": "Maya"}).status_code, 200)

    def test_owner_can_edit_a_note_and_change_its_privacy(self):
        self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Maya", "private": True, "answers": {"travel": "Budget $100 a day"}})
        mid = next(m["id"] for m in self.view("Maya")["memories"] if m["traveler"] == "Maya")
        url = f"/api/trips/{self.id}/memories/{mid}"
        self.assertEqual(self.c.patch(url, json={"me": "Priya", "private": False}).status_code, 403)   # not hers
        self.assertEqual(self.c.patch(url, json={"me": "Maya", "text": "  "}).status_code, 400)
        r = self.c.patch(url, json={"me": "Maya", "text": "Budget $150 a day"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("$150", self.c.get(f"/api/trips/{self.id}", params={"me": "Priya"}).text)  # edit kept it private
        self.assertEqual(self.c.patch(url, json={"me": "Maya", "private": False}).status_code, 200)
        note = next(m for m in self.view("Priya")["memories"] if m["id"] == mid)
        self.assertEqual((note["text"], note["private"], note["kind"]), ("Budget $150 a day", False, "travel"))
        self.assertFalse(note["can_edit"])
        self.assertTrue(next(m for m in self.view("Maya")["memories"] if m["id"] == mid)["can_edit"])

    def test_only_members_can_add(self):
        r = self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Stranger", "answers": {"diet": "x"}})
        self.assertEqual(r.status_code, 400)

    def test_packing_list(self):
        self.c.post(f"/api/trips/{self.id}/packing", json={"me": "Priya", "text": "Sunscreen, speaker"})
        self.assertEqual(self.c.post(f"/api/trips/{self.id}/packing", json={"me": "Maya", "text": "sunscreen"}).status_code, 400)
        items = self.view()["trip"]["packing"]
        self.assertEqual([i["text"] for i in items], ["Sunscreen", "speaker"])
        self.c.patch(f"/api/trips/{self.id}/packing/{items[0]['id']}", json={"done": True})
        self.c.delete(f"/api/trips/{self.id}/packing/{items[1]['id']}")
        self.assertEqual([(i["text"], i["done"]) for i in self.view()["trip"]["packing"]], [("Sunscreen", True)])

    def test_propose_vote_choose_plan(self):
        self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Priya", "answers": {"travel": "I love hiking"}})
        r = self.c.post(f"/api/trips/{self.id}/proposals")
        self.assertEqual(r.json()["engine"], "rules")
        props = self.view()["trip"]["proposals"]
        self.assertGreaterEqual(len(props), 3)
        pid = props[0]["id"]
        self.assertEqual(self.c.post(f"/api/trips/{self.id}/votes", json={"me": "Maya", "proposal_id": pid}).json()["voters"], ["Maya"])
        self.assertEqual(self.c.post(f"/api/trips/{self.id}/votes", json={"me": "Maya", "proposal_id": pid}).json()["voters"], [])
        self.assertEqual(self.c.post(f"/api/trips/{self.id}/choose", json={"proposal_id": pid}).status_code, 200)
        trip = self.view()["trip"]
        self.assertEqual(trip["chosen"]["id"], pid)
        self.assertTrue(trip["plan"]["days"])
        own = self.c.post(f"/api/trips/{self.id}/choose", json={"destination": "Lake Tahoe"})
        self.assertEqual(own.json()["destination"], "Lake Tahoe")
        self.assertEqual(self.c.post(f"/api/trips/{self.id}/plan").status_code, 200)
        self.assertEqual(self.view()["limits"]["plan_left"], server.MAX_PLANS - 3)

    def test_feedback_is_remembered_on_the_next_trip_of_the_same_crew(self):
        self.c.post(f"/api/trips/{self.id}/feedback", json={"me": "Maya", "text": "Too much driving"})
        self.c.post(f"/api/trips/{self.id}/notes", json={"me": "Maya", "answers": {"place": "A lake"}})
        nxt = self.c.post("/api/trips", json={"name": "Trip 2", "members": "Maya", "earlier": f"?trip={self.id}"}).json()["id"]
        texts = [m["text"] for m in self.c.get(f"/api/trips/{nxt}", params={"me": "Maya"}).json()["memories"]]
        self.assertIn("Too much driving", texts)   # feedback carries over
        self.assertNotIn("A lake", texts)          # places belong to one trip

    def test_delete_trip(self):
        self.assertEqual(self.c.delete(f"/api/trips/{self.id}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/trips/{self.id}").status_code, 404)

    def test_access_code(self):
        server.CREATE_CODE = "sesame"
        try:
            self.assertEqual(self.c.post("/api/trips", json={"name": "x", "members": "A"}).status_code, 403)
            self.assertEqual(self.c.post("/api/trips", json={"name": "x", "members": "A", "code": "sesame"}).status_code, 200)
            self.assertTrue(self.c.get("/api/config").json()["create_code_required"])
        finally:
            server.CREATE_CODE = ""


if __name__ == "__main__":
    unittest.main()
