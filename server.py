"""
WanderFolk web API. The React app in web/ talks to this; planner.py, memory_store.py and llm.py do the real work.

Run locally:   .venv/bin/uvicorn server:app --reload --port 8000     (and `npm run dev` in web/)
On Vercel:     this file is the Python entrypoint (see pyproject.toml); the built web app is served from public/.

Privacy: everything that is someone else's private note is filtered out HERE, before it reaches the browser.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import llm  # noqa: E402
import planner  # noqa: E402
from memory_store import APP_ID, make_store, make_trip_store, traveler_id  # noqa: E402

BUCKET = "trips"
MAX_MEMBERS = 12
MAX_SUGGESTS, MAX_PLANS = 6, 15                     # AI runs per trip, so one trip can't run up the bill
CREATE_CODE = os.getenv("CREATE_CODE", "").strip()  # if set, starting a trip needs this code; joining never does

# kind -> (icon, question, example): what each person can tell WanderFolk before a trip.
CATEGORIES = {
    "place": ("📍", "Places I'd love to go", "e.g. Somewhere with a lake, or Lake Tahoe"),
    "diet": ("🥗", "Food and dietary needs", "e.g. Vegetarian, allergic to peanuts"),
    "travel": ("🚗", "How I like to travel", "e.g. Short drives, relaxed pace, mid budget"),
    "idea": ("💡", "My idea for this trip", "e.g. Rent a cabin and do a BBQ night"),
}
REMEMBERED = {"diet", "travel", "feedback"}  # true of the person, not just this trip: carried to their next trips

store, store_warning = make_store()
trips_db = make_trip_store()

app = FastAPI(title="WanderFolk", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_names(raw: str) -> list[str]:
    """'Priya, arjun\\nPriya' -> ['Priya', 'arjun'] (commas or new lines, no repeats)."""
    names: list[str] = []
    for name in re.split(r"[,\n]+", raw or ""):
        name = name.strip()[:40]
        if name and name.lower() not in [n.lower() for n in names]:
            names.append(name)
    return names


def find_trip(text: str) -> dict | None:
    """Accepts a trip code or a whole invite link."""
    text = (text or "").strip()
    link = re.search(r"[?&]trip=([^&\s#]+)", text)
    trip_id = unquote(link.group(1)) if link else text
    return trips_db.get(BUCKET, trip_id) if trip_id else None


def load(trip_id: str) -> dict:
    trip = trips_db.get(BUCKET, trip_id)
    if not trip:
        raise HTTPException(404, "That link doesn't match a trip. Check it with whoever sent it.")
    return trip


def save(trip: dict) -> None:
    trips_db.save(BUCKET, trip)


def crew_of(trip: dict) -> str:
    return trip.get("crew") or "roamory"


def check_member(trip: dict, name: str) -> str:
    if name not in trip["members"]:
        raise HTTPException(400, "Pick who you are first.")
    return name


# What Mem0 holds for a crew, kept briefly so every page load isn't a round trip. Cleared on every write.
_mem_cache: dict[str, tuple[float, list[dict]]] = {}
_mem_lock = threading.Lock()


def _forget_cache(trip: dict) -> None:
    with _mem_lock:
        _mem_cache.pop(trip["id"], None)


def trip_memories(trip: dict) -> list[dict]:
    """Everything that counts for this trip: what people said for it, plus what they told earlier trips of this crew."""
    with _mem_lock:
        hit = _mem_cache.get(trip["id"])
    if hit and time.time() - hit[0] < 20:
        found = hit[1]
    else:
        ids = [traveler_id(crew_of(trip), p) for p in trip["members"]]
        try:
            found = store.for_travelers(ids)
        except Exception as e:
            print(f"[memory] read failed: {e.__class__.__name__}: {e}")
            found = []
        with _mem_lock:
            _mem_cache[trip["id"]] = (time.time(), found)
    out = []
    for m in found:
        if m.get("group") == crew_of(trip) and m.get("traveler") in trip["members"] \
                and (m.get("trip_id") == trip["id"] or m.get("type") in REMEMBERED):
            out.append({**m, "traveler_name": m["traveler"]})
    return out


def remember(trip: dict, name: str, text: str, kind: str, private: bool = False) -> None:
    meta = {"type": kind, "traveler": name, "private": private, "group": crew_of(trip),
            "trip_id": trip["id"], "trip_name": trip["name"]}
    try:
        store.add(text[:1000], traveler_id(crew_of(trip), name), meta, run_id=trip["id"] if kind == "feedback" else None)
    except Exception as e:
        raise HTTPException(502, f"Couldn't save that ({e.__class__.__name__}). Try again in a moment.")
    finally:
        _forget_cache(trip)


def note_view(m: dict, trip: dict, me: str | None) -> dict:
    """One memory as the person looking at the screen may see it. Someone else's private note loses its text."""
    hidden = bool(m.get("private")) and m.get("traveler") != me
    return {
        "id": m["id"], "traveler": m["traveler"], "kind": m.get("type"), "private": bool(m.get("private")),
        "text": None if hidden else m["memory"], "mine": m.get("traveler") == me,
        "from_trip": m.get("trip_name") if m.get("trip_id") != trip["id"] else None,
        "can_delete": not hidden and me is not None,
    }


def trip_view(trip: dict, me: str | None) -> dict:
    memories = trip_memories(trip)
    notes = [m for m in memories if m.get("type") in CATEGORIES]
    public = {k: v for k, v in trip.items() if k != "crew"}
    return {
        "trip": public,
        "memories": [note_view(m, trip, me) for m in memories],
        "waiting_on": [p for p in trip["members"] if not any(m["traveler"] == p for m in notes)],
        "limits": {"suggest_left": MAX_SUGGESTS - trip.get("suggest_runs", 0),
                   "plan_left": MAX_PLANS - trip.get("plan_runs", 0)},
    }


def make_plan(trip: dict) -> None:
    if trip.get("plan_runs", 0) >= MAX_PLANS:
        raise HTTPException(429, f"This trip has reached its limit of {MAX_PLANS} plans.")
    memories = trip_memories(trip)
    trip["plan"] = planner.plan_trip(trip["chosen"]["destination"], int(trip["days"]), trip["members"], memories)
    trip["memories_used"], trip["plan_runs"] = len(memories), trip.get("plan_runs", 0) + 1


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class NewTrip(BaseModel):
    name: str = Field(max_length=80)
    origin: str = Field("", max_length=80)
    days: int = Field(3, ge=1, le=7)
    members: str = Field(max_length=1000)
    earlier: str = Field("", max_length=300)
    code: str = Field("", max_length=100)


class EditTrip(BaseModel):
    origin: str = Field("", max_length=80)
    days: int = Field(ge=1, le=7)
    members: str = Field(max_length=1000)


class Notes(BaseModel):
    me: str
    answers: dict[str, str]
    private: bool = False


class Text(BaseModel):
    me: str
    text: str = Field(max_length=1000)


class Done(BaseModel):
    done: bool


class Vote(BaseModel):
    me: str
    proposal_id: str


class Choose(BaseModel):
    proposal_id: str | None = None
    destination: str | None = Field(None, max_length=100)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/config")
def config():
    return {
        "create_code_required": bool(CREATE_CODE),
        "max_members": MAX_MEMBERS,
        "categories": [{"kind": k, "icon": i, "question": q, "example": e} for k, (i, q, e) in CATEGORIES.items()],
        "status": {
            "memory": {"label": store.name + ("" if store.is_live else " (offline mode)"), "on": store.is_live},
            "ai": {"label": llm.provider_label(), "on": llm.provider() is not None},
            "trips": {"label": trips_db.name, "on": trips_db.name != "Local file"},
            "warning": store_warning,
        },
        "app_id": APP_ID,
    }


@app.get("/api/lookup")
def lookup(link: str):
    trip = find_trip(link)
    if not trip:
        raise HTTPException(404, "That doesn't match a trip. Check it with whoever sent it.")
    return {"id": trip["id"], "name": trip["name"]}


@app.post("/api/trips")
def create_trip(body: NewTrip):
    people = parse_names(body.members)
    earlier = find_trip(body.earlier) if body.earlier.strip() else None
    if CREATE_CODE and body.code.strip() != CREATE_CODE:
        raise HTTPException(403, "That access code isn't right. Ask whoever runs this app for it.")
    if not body.name.strip():
        raise HTTPException(400, "Give the trip a name.")
    if not people:
        raise HTTPException(400, "Add at least one person.")
    if len(people) > MAX_MEMBERS:
        raise HTTPException(400, f"That's {len(people)} people. WanderFolk handles up to {MAX_MEMBERS} for now.")
    if body.earlier.strip() and not earlier:
        raise HTTPException(400, "That earlier trip link doesn't match a trip. Fix it or leave the box empty.")
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")[:40] or "trip"
    trip = {"id": f"{slug}-{uuid.uuid4().hex[:10]}", "name": body.name.strip(),
            # crew: the group of friends. Trips that share a crew share what WanderFolk knows about each person.
            "crew": earlier["crew"] if earlier and earlier.get("crew") else uuid.uuid4().hex[:10],
            "origin": body.origin.strip(), "days": body.days, "members": people,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "packing": [], "proposals": [], "votes": {}, "chosen": None, "plan": None}
    save(trip)
    return {"id": trip["id"]}


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str, me: str | None = None):
    trip = load(trip_id)
    return trip_view(trip, me if me in trip["members"] else None)


@app.patch("/api/trips/{trip_id}")
def edit_trip(trip_id: str, body: EditTrip):
    trip = load(trip_id)
    people = parse_names(body.members)
    if not people:
        raise HTTPException(400, "Keep at least one person.")
    if len(people) > MAX_MEMBERS:
        raise HTTPException(400, f"That's {len(people)} people. The limit is {MAX_MEMBERS}.")
    trip.update(origin=body.origin.strip(), days=body.days, members=people)
    save(trip)
    _forget_cache(trip)
    return {"ok": True}


@app.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: str):
    trip = load(trip_id)
    for m in trip_memories(trip):  # this trip's places and ideas go; diet, travel style and feedback stay remembered
        if m.get("trip_id") == trip["id"] and m.get("type") not in REMEMBERED:
            store.delete(m["id"])
    trips_db.delete(BUCKET, trip["id"])
    _forget_cache(trip)
    return {"ok": True}


@app.post("/api/trips/{trip_id}/notes")
def add_notes(trip_id: str, body: Notes):
    trip = load(trip_id)
    me = check_member(trip, body.me)
    filled = {k: v.strip() for k, v in body.answers.items() if k in CATEGORIES and v and v.strip()}
    if not filled:
        raise HTTPException(400, "Fill in at least one box first.")
    for kind, text in filled.items():
        remember(trip, me, text, kind, body.private)
    return {"saved": len(filled)}


@app.post("/api/trips/{trip_id}/feedback")
def add_feedback(trip_id: str, body: Text):
    trip = load(trip_id)
    me = check_member(trip, body.me)
    if not body.text.strip():
        raise HTTPException(400, "Type something first.")
    remember(trip, me, body.text.strip(), "feedback")
    return {"ok": True}


@app.delete("/api/trips/{trip_id}/memories/{memory_id}")
def delete_memory(trip_id: str, memory_id: str, me: str):
    trip = load(trip_id)
    m = next((m for m in trip_memories(trip) if m["id"] == memory_id), None)
    if not m:
        raise HTTPException(404, "That note is already gone.")
    if m.get("private") and m.get("traveler") != me:
        raise HTTPException(403, "Only its owner can delete a private note.")
    store.delete(memory_id)
    _forget_cache(trip)
    return {"ok": True}


@app.get("/api/trips/{trip_id}/search")
def search(trip_id: str, q: str, me: str | None = None):
    trip = load(trip_id)
    ids = [traveler_id(crew_of(trip), p) for p in trip["members"]]
    try:
        hits = store.search(q[:200], user_ids=ids)
    except Exception as e:
        raise HTTPException(502, f"Search failed ({e.__class__.__name__}).")
    hits = [m for m in hits if m.get("group") == crew_of(trip) and m.get("traveler") in trip["members"]]
    return {"hits": [note_view(m, trip, me) for m in hits]}


# ---- packing list ----

@app.post("/api/trips/{trip_id}/packing")
def add_packing(trip_id: str, body: Text):
    trip = load(trip_id)
    me = check_member(trip, body.me)
    have = {i["text"].lower() for i in trip["packing"]}
    fresh = [t for t in parse_names(body.text) if t.lower() not in have]
    if not fresh:
        raise HTTPException(400, "Type something new first.")
    trip["packing"] += [{"id": uuid.uuid4().hex[:8], "text": t, "by": me, "done": False} for t in fresh]
    save(trip)
    return {"added": len(fresh)}


@app.post("/api/trips/{trip_id}/packing/suggested")
def add_suggested(trip_id: str):
    trip = load(trip_id)
    have = {i["text"].lower() for i in trip["packing"]}
    fresh = [s for s in ((trip.get("plan") or {}).get("packing") or []) if s.lower() not in have]
    trip["packing"] += [{"id": uuid.uuid4().hex[:8], "text": t, "by": "WanderFolk", "done": False} for t in fresh]
    save(trip)
    return {"added": len(fresh)}


@app.patch("/api/trips/{trip_id}/packing/{item_id}")
def tick_packing(trip_id: str, item_id: str, body: Done):
    trip = load(trip_id)
    for item in trip["packing"]:
        if item["id"] == item_id:
            item["done"] = body.done
    save(trip)
    return {"ok": True}


@app.delete("/api/trips/{trip_id}/packing/{item_id}")
def remove_packing(trip_id: str, item_id: str):
    trip = load(trip_id)
    trip["packing"] = [i for i in trip["packing"] if i["id"] != item_id]
    save(trip)
    return {"ok": True}


# ---- proposals, votes, the chosen place and its plan ----

@app.post("/api/trips/{trip_id}/proposals")
def suggest(trip_id: str):
    trip = load(trip_id)
    if trip.get("suggest_runs", 0) >= MAX_SUGGESTS:
        raise HTTPException(429, f"This trip has had its {MAX_SUGGESTS} rounds of proposals.")
    found, engine = planner.propose_trips(trip.get("origin", ""), int(trip["days"]), trip["members"],
                                          trip_memories(trip))
    trip = load(trip_id)  # re-read: people may have voted or packed while the AI was thinking
    trip.update(proposals=[{"id": uuid.uuid4().hex[:8], **p} for p in found], votes={}, proposals_engine=engine,
                suggest_runs=trip.get("suggest_runs", 0) + 1)
    save(trip)
    return {"count": len(found), "engine": engine}


@app.post("/api/trips/{trip_id}/votes")
def vote(trip_id: str, body: Vote):
    trip = load(trip_id)
    me = check_member(trip, body.me)
    if not any(p["id"] == body.proposal_id for p in trip["proposals"]):
        raise HTTPException(404, "That proposal is gone. Refresh to see the latest ones.")
    voters = [p for p in trip["votes"].get(body.proposal_id, []) if p in trip["members"]]
    trip["votes"][body.proposal_id] = [p for p in voters if p != me] if me in voters else voters + [me]
    save(trip)
    return {"voters": trip["votes"][body.proposal_id]}


@app.post("/api/trips/{trip_id}/choose")
def choose(trip_id: str, body: Choose):
    trip = load(trip_id)
    if body.destination and body.destination.strip():
        prop = {"id": "own", "destination": body.destination.strip(), "tagline": "The group's own pick", "why": [],
                "watch_out": "", "travel": "", "budget": "", "highlights": []}
    else:
        prop = next((p for p in trip["proposals"] if p["id"] == body.proposal_id), None)
        if not prop:
            raise HTTPException(400, "Pick a proposal or type a destination first.")
    trip["chosen"] = prop
    make_plan(trip)
    save(trip)
    return {"destination": prop["destination"]}


@app.post("/api/trips/{trip_id}/plan")
def replan(trip_id: str):
    trip = load(trip_id)
    if not trip.get("chosen"):
        raise HTTPException(400, "Choose a destination first.")
    make_plan(trip)
    save(trip)
    return {"ok": True}


# ---------------------------------------------------------------------------
# The built web app. On Vercel, public/ is served by the CDN before this is reached; locally this serves it.
# ---------------------------------------------------------------------------

PUBLIC = Path(__file__).parent / "public"
if (PUBLIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=PUBLIC / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        file = (PUBLIC / path).resolve()
        if path and file.is_file() and PUBLIC.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(PUBLIC / "index.html")
