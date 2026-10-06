"""Run: python -m unittest discover tests -v   (no keys or internet needed)"""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ANTHROPIC_API_KEY", None); os.environ.pop("OPENAI_API_KEY", None)
import planner
from memory_store import LocalStore, traveler_id


def m(who, text, kind="preference", private=False, trip=""):
    return {"memory": text, "traveler": who, "traveler_name": who, "type": kind, "private": private, "trip_name": trip}


PREFS = [m(n, t, private=p) for n, t, p in planner.DEMO_PREFERENCES]
FEEDBACK = [m(n, t, "feedback", trip="Santa Cruz (trip 1)") for n, t in planner.DEMO_FEEDBACK]


def times(plan, word):
    return [i["time"] for d in plan["days"] for i in d["items"] if word in i["activity"].lower()]


class Planning(unittest.TestCase):
    def test_trip1_uses_preferences(self):
        plan = planner.plan_trip("Santa Cruz", 2, planner.DEMO_TRAVELERS, PREFS)
        actions = {c["key"]: c for c in plan["changes"]}
        self.assertEqual(actions["hiking"]["who"], "Priya")
        self.assertEqual(actions["vegetarian"]["who"], "Arjun")
        self.assertEqual(times(plan, "hike"), ["7:00 AM"])         # nobody has complained yet
        self.assertTrue(times(plan, "drive"))                     # day trip by car

    def test_trip2_learns_from_feedback(self):
        plan = planner.plan_trip("Big Sur", 2, planner.DEMO_TRAVELERS, PREFS + FEEDBACK)
        actions = {c["key"]: c for c in plan["changes"]}
        self.assertEqual(times(plan, "hike"), ["10:30 AM"])        # Priya: 7am was too early
        self.assertFalse(times(plan, "drive"))                     # Maya: too much driving
        self.assertIn("Sunscreen (everyone!)", plan["packing"])    # forgot sunscreen
        for key in ("late_start", "less_driving", "sunscreen", "local_food"):
            self.assertEqual(actions[key]["kind"], "feedback", key)
            self.assertEqual(actions[key]["trip"], "Santa Cruz (trip 1)")
        self.assertEqual(actions["hiking"]["kind"], "preference")  # likes still credited to the preference

    def test_no_memories_still_plans(self):
        plan = planner.plan_trip("Tahoe", 1, ["A"], [])
        self.assertEqual(len(plan["days"]), 1)
        self.assertEqual(plan["changes"], [])


class Community(unittest.TestCase):
    def test_wheelchair_uses_other_travelers_tips(self):
        need = m(*planner.DEMO_NEW_NEED[:2])
        tips = [{"memory": t, "type": "community", "traveler_name": "another traveler"}
                for t in planner.DEMO_COMMUNITY["Big Sur"]]
        plan = planner.plan_trip("Big Sur", 2, planner.DEMO_TRAVELERS, PREFS + FEEDBACK + [need] + tips)
        actions = [c["action"] for c in plan["changes"] if c["kind"] == "community"]
        self.assertIn("Added McWay Falls overlook", actions)
        self.assertIn("Skipped Pfeiffer Beach", actions)
        self.assertNotIn("Pfeiffer", str(plan["days"]))
        self.assertFalse(times(plan, "coastal hike"))            # hike swapped for a step-free walk

    def test_tips_dont_become_our_preferences(self):
        tips = [{"memory": "Pfeiffer Beach has a steep sandy path, not good for wheelchairs", "type": "community"}]
        keys = {c["key"] for c in planner.plan_trip("Big Sur", 1, ["A"], tips)["changes"]}
        self.assertNotIn("accessible", keys)                    # nobody in OUR group needs it
        self.assertNotIn("avoid", keys)

    def test_days_sorted(self):
        plan = planner.plan_trip("Big Sur", 2, planner.DEMO_TRAVELERS, PREFS + FEEDBACK)
        for d in plan["days"]:
            ks = [planner.time_key(i["time"]) for i in d["items"]]
            self.assertEqual(ks, sorted(ks))


class Privacy(unittest.TestCase):
    def test_private_note_never_named(self):
        plan = planner.plan_trip("Big Sur", 2, planner.DEMO_TRAVELERS, PREFS + FEEDBACK)
        budget = next(c for c in plan["changes"] if c["key"] == "budget")
        self.assertTrue(budget["private"])
        self.assertEqual(budget["who"], "private")
        self.assertNotIn("$100", str(plan))

    def test_guard_redacts_a_leaky_ai_plan(self):
        leaky = {"days": [{"day": 1, "items": [{"time": "1 PM", "activity": "Cheap lunch to stay under $100"}]}],
                 "changes": [{"action": "Cheap picks", "because": "Maya's budget is $100", "who": "Maya",
                              "private": False, "kind": "preference"}], "packing": []}
        plan, n = planner.privacy_guard(leaky, PREFS)
        self.assertNotIn("$100", str(plan))
        self.assertEqual(plan["changes"][0]["who"], "private")
        self.assertGreaterEqual(n, 2)


class MemoryScopes(unittest.TestCase):
    def setUp(self):
        self.store = LocalStore(Path(tempfile.mkdtemp()) / "m.json")

    def test_scopes(self):
        p, a = traveler_id("Crew", "Priya"), traveler_id("Crew", "Arjun")
        self.store.add("loves hiking", p, {"type": "preference", "traveler": "Priya", "group": "Crew"})
        self.store.add("7am too early", p, {"type": "feedback", "traveler": "Priya", "group": "Crew"}, run_id="t1")
        self.store.add("loved tacos", a, {"type": "feedback", "traveler": "Arjun", "group": "Crew"}, run_id="t1")
        self.assertEqual(len(self.store.for_traveler(p)), 2)     # user_id scope
        self.assertEqual(len(self.store.for_trip("t1")), 2)      # run_id scope (shared trip memory)
        self.assertEqual(len(self.store.shared()), 3)            # agent_id + app_id scope (everyone)
        self.assertEqual(self.store.search("tacos")[0]["traveler"], "Arjun")
        self.store.clear_group([p])
        self.assertEqual(len(self.store.shared()), 1)

    def test_groups_dont_collide(self):
        self.assertNotEqual(traveler_id("Crew A", "Priya"), traveler_id("Crew B", "Priya"))



class Proposals(unittest.TestCase):
    def test_offline_proposals_follow_what_the_group_said(self):
        notes = [m("Priya", "I'd love a lake and some hiking", "place"), m("Arjun", "A cabin in the mountains", "idea")]
        proposals, engine = planner.propose_trips("San Francisco", 3, ["Priya", "Arjun"], notes)
        self.assertEqual(engine, "rules")                              # no AI key in tests
        self.assertTrue(5 <= len(proposals) <= 6)
        self.assertEqual(proposals[0]["destination"], "Lake Tahoe, California")
        self.assertTrue(any("Priya" in reason for reason in proposals[0]["why"]))

    def test_proposals_never_quote_private_notes(self):
        notes = [m("Maya", "My budget is about $100 a day, keep it cheap", "travel", private=True)]
        proposals, _ = planner.propose_trips("San Francisco", 2, ["Maya"], notes)
        text = " ".join(" ".join(p["why"]) + p["tagline"] + p["watch_out"] for p in proposals)
        self.assertNotIn("$100", text)
        self.assertNotIn("Maya", text)


if __name__ == "__main__":
    unittest.main()
