"""
WanderFolk: a simple travel planner agent for a group of friends.
Run with:  streamlit run app.py

Create a trip, add up to 12 people, let everyone say where they'd love to go, what they eat, how they like to
travel and what to pack. WanderFolk proposes 5-6 destinations, the group picks one, and it shows the Google Map,
an itinerary and the reason behind every choice.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime
from urllib.parse import quote, quote_plus, unquote, urlsplit

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

import llm  # noqa: E402
import planner  # noqa: E402
import style  # noqa: E402
from memory_store import APP_ID, TripStore, make_store, traveler_id  # noqa: E402

st.set_page_config(page_title="WanderFolk", page_icon="🏔️", layout="wide")
st.markdown(style.CSS, unsafe_allow_html=True)

BUCKET = "trips"          # key for this app's trips in the local trips file
MAX_MEMBERS = 12
MAX_SUGGESTS, MAX_PLANS = 6, 15                   # AI runs per trip, so one trip can't run up the bill
CREATE_CODE = os.getenv("CREATE_CODE", "").strip()  # if set, starting a trip needs this code; joining never does

T_INPUT, T_PACK, T_PROPS = "📝 Everyone's input", "🎒 Packing list", "💡 Proposals"
T_TRIP, T_AFTER, T_MEMORY = "🗺️ Our trip", "💬 After the trip", "🧠 Memory"

# kind -> (icon, question, example). These are what each person can tell WanderFolk before a trip.
CATEGORIES = {
    "place": ("📍", "Places I'd love to go", "e.g. Somewhere with a lake, or Lake Tahoe"),
    "diet": ("🥗", "Food and dietary needs", "e.g. Vegetarian, allergic to peanuts"),
    "travel": ("🚗", "How I like to travel", "e.g. Short drives, relaxed pace, mid budget"),
    "idea": ("💡", "My idea for this trip", "e.g. Rent a cabin and do a BBQ night"),
}
ICONS = {kind: icon for kind, (icon, _, _) in CATEGORIES.items()} | {"feedback": "💬"}
REMEMBERED = {"diet", "travel", "feedback"}  # true of the person, not just this trip: carried to their next trips


@st.cache_resource
def get_store():
    return make_store()


store, store_warning = get_store()
trips_db = TripStore()
ss = st.session_state


def flash(message: str) -> None:
    """Show a toast after the next rerun (a toast sent right before st.rerun() is lost)."""
    ss["flash"] = message


def goto(tab: str) -> None:
    ss["tab"] = tab


def parse_names(raw: str) -> list[str]:
    """'Priya, arjun\\nPriya' -> ['Priya', 'arjun'] (commas or new lines, no repeats)."""
    names = []
    for name in re.split(r"[,\n]+", raw):
        name = name.strip()
        if name and name.lower() not in [n.lower() for n in names]:
            names.append(name)
    return names


def maps_search(place: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(place)}"


def find_trip(text: str) -> dict | None:
    """Accepts a trip code or a whole invite link."""
    link = re.search(r"[?&]trip=([^&\s]+)", text)
    return trips_db.get(BUCKET, unquote(link.group(1)) if link else text.strip())


def open_trip(trip_id: str) -> None:
    st.query_params["trip"] = trip_id
    st.rerun()


# A widget's value can't be changed once it's on the page, so a tab jump set here applies at the start of the next run.
if "goto_tab" in ss:
    ss["tab"] = ss.pop("goto_tab")
if "flash" in ss:
    st.toast(ss.pop("flash"))

with st.sidebar:
    st.title("🏔️ WanderFolk")
    st.caption("A simple travel planner agent for your group.")

# ---------------------------------------------------------------------------
# No trip open: start one, or join one with its link. There is no public list of trips.
# ---------------------------------------------------------------------------

trip = trips_db.get(BUCKET, st.query_params.get("trip", ""))

if not trip:
    st.markdown(style.hero(), unsafe_allow_html=True)
    if st.query_params.get("trip"):
        st.warning("That link doesn't match a trip. Check it with whoever sent it, or start a new trip.")
    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.subheader("Start a group trip")
        st.caption("Name the trip and add who's coming. You don't need a destination yet: "
                   "WanderFolk will propose some once everyone has had their say.")
        with st.form("new_trip", border=False):
            a, b, c = st.columns([3, 2, 1])
            name_in = a.text_input("Trip name", placeholder="e.g. Summer getaway 2026")
            origin_in = b.text_input("Starting from", placeholder="e.g. San Francisco")
            days_in = c.number_input("Days", 1, 7, 3)
            members_in = st.text_area(f"Who's coming? (up to {MAX_MEMBERS})", height=120,
                                      placeholder="One name per line, or separated by commas")
            earlier_in = st.text_input("Travelled together before? (optional)",
                                       placeholder="Paste that trip's link to carry over dietary needs and feedback")
            code_in = st.text_input("Access code", type="password") if CREATE_CODE else ""
            if st.form_submit_button("Create trip", type="primary"):
                people = parse_names(members_in)
                earlier = find_trip(earlier_in) if earlier_in.strip() else None
                if CREATE_CODE and code_in.strip() != CREATE_CODE:
                    st.warning("That access code isn't right. Ask whoever runs this app for it.")
                elif not name_in.strip():
                    st.warning("Give the trip a name.")
                elif not people:
                    st.warning("Add at least one person.")
                elif len(people) > MAX_MEMBERS:
                    st.warning(f"That's {len(people)} people. WanderFolk handles up to {MAX_MEMBERS} for now.")
                elif earlier_in.strip() and not earlier:
                    st.warning("That earlier trip link doesn't match a trip. Fix it or leave the box empty.")
                else:
                    slug = re.sub(r"[^a-z0-9]+", "-", name_in.lower()).strip("-") or "trip"
                    # crew: the group of friends. Trips that share a crew share what WanderFolk knows about each person.
                    new = {"id": f"{slug}-{uuid.uuid4().hex[:10]}", "name": name_in.strip(),
                           "crew": earlier["crew"] if earlier and earlier.get("crew") else uuid.uuid4().hex[:10],
                           "origin": origin_in.strip(), "days": int(days_in), "members": people,
                           "created_at": datetime.now().isoformat(timespec="seconds"),
                           "packing": [], "proposals": [], "votes": {}, "chosen": None, "plan": None}
                    trips_db.save(BUCKET, new)
                    flash(f"{new['name']} created. Invite the others with the link.")
                    open_trip(new["id"])
    with right, st.container(border=True):
        st.subheader("Join a trip")
        st.caption("Got a link from a friend? Open it, or paste it here.")
        with st.form("join_trip", border=False):
            link_in = st.text_input("Trip link or code", placeholder="Paste it here")
            if st.form_submit_button("Open trip"):
                found = find_trip(link_in)
                if found:
                    open_trip(found["id"])
                st.warning("That doesn't match a trip. Check it with whoever sent it.")
        # Only on your own computer: a hosted app must never list other people's trips.
        if urlsplit(st.context.url or "").hostname in ("localhost", "127.0.0.1"):
            for t in sorted(trips_db.list(BUCKET), key=lambda t: t["created_at"], reverse=True):
                if st.button(f"🗺️ {t['name']}", key=f"open_{t['id']}", width="stretch"):
                    open_trip(t["id"])
    st.stop()

members = trip["members"]
crew = trip.get("crew") or "roamory"
people_ids = [traveler_id(crew, person) for person in members]
invite_link = f"{(st.context.url or '').split('?')[0]}?trip={quote(trip['id'])}"


def save_trip() -> None:
    trips_db.save(BUCKET, trip)

# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------


def remember(name: str, text: str, kind: str, private: bool = False) -> bool:
    meta = {"type": kind, "traveler": name, "private": private, "group": crew,
            "trip_id": trip["id"], "trip_name": trip["name"]}
    try:
        store.add(text, traveler_id(crew, name), meta, run_id=trip["id"] if kind == "feedback" else None)
    except Exception as e:
        st.error(f"Couldn't save that ({e.__class__.__name__}). Check your connection and try again.")
        return False
    ss.pop("mem", None)
    return True


def forget(memory_id: str) -> None:
    store.delete(memory_id)
    ss.pop("mem", None)


def read_memories() -> tuple[list[dict], str]:
    """What Mem0 holds for this group's people, kept for 30 seconds so every click isn't a round trip."""
    cache = ss.get("mem")
    if not cache or cache["trip"] != trip["id"] or cache["people"] != people_ids or time.time() - cache["at"] > 30:
        try:
            found = store.for_travelers(people_ids)
        except Exception:
            found = []
        cache = ss["mem"] = {"trip": trip["id"], "people": people_ids, "at": time.time(), "items": found}
    return cache["items"], f"Mem0 user_id scopes for this group ({len(people_ids)} people), app_id={APP_ID}"


everything, scope_label = read_memories()
# What counts for this trip: what people said for it, plus what WanderFolk already knows about them from earlier trips.
memories = [m for m in everything if m.get("group") == crew and m.get("traveler") in members
            and (m.get("trip_id") == trip["id"] or m.get("type") in REMEMBERED)]
for m in memories:
    m["traveler_name"] = m["traveler"]
notes = [m for m in memories if m.get("type") in CATEGORIES]
no_input_yet = [p for p in members if not any(m["traveler"] == p for m in notes)]

# ---------------------------------------------------------------------------
# Sidebar: this trip
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("##### Invite the group")
    st.caption("Anyone with this link can open the trip and add their input. Share it only with the group.")
    st.code(invite_link, language=None, wrap_lines=True)
    if st.button("← Leave this trip", width="stretch", help="Back to the start page. Nothing is deleted."):
        del st.query_params["trip"]
        st.rerun()
    if st.button("🔄 Refresh", width="stretch", help="Pick up anything added from another device."):
        ss.pop("mem", None)
        st.rerun()
    with st.expander("✏️ Edit this trip"):
        with st.form("edit_trip", border=False):
            origin_edit = st.text_input("Starting from", value=trip.get("origin", ""))
            days_edit = st.number_input("Days", 1, 7, int(trip.get("days", 3)))
            members_edit = st.text_area(f"Who's coming? (up to {MAX_MEMBERS})", value="\n".join(members), height=160)
            if st.form_submit_button("Save"):
                people = parse_names(members_edit)
                if not people:
                    st.warning("Keep at least one person.")
                elif len(people) > MAX_MEMBERS:
                    st.warning(f"That's {len(people)} people. The limit is {MAX_MEMBERS}.")
                else:
                    trip.update(origin=origin_edit.strip(), days=int(days_edit), members=people)
                    save_trip()
                    flash("Trip updated")
                    st.rerun()
    with st.expander("⚙️ Under the hood"):
        st.markdown(style.status("Memory", store.name + ("" if store.is_live else " (offline mode)"), store.is_live)
                    + style.status("AI model", llm.provider_label(), llm.provider() is not None),
                    unsafe_allow_html=True)
        if store_warning:
            st.warning(store_warning)
    with st.expander("🧹 Delete this trip"):
        st.caption(f"Deletes **{trip['name']}** with its ideas, packing list and plan. Dietary needs, travel "
                   "style and feedback stay remembered for each person's next trip. This can't be undone.")
        sure = st.checkbox("Yes, delete it")
        if st.button("Delete trip", disabled=not sure):
            for m in memories:
                if m.get("trip_id") == trip["id"] and m.get("type") not in REMEMBERED:
                    store.delete(m["id"])
            trips_db.delete(BUCKET, trip["id"])
            ss.pop("mem", None)
            flash("Trip deleted")
            del st.query_params["trip"]
            st.rerun()

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def visible(m: dict) -> str:
    """What the person currently adding is allowed to see of a note."""
    if m.get("private") and m.get("traveler") != me:
        return "🔒 Private note"
    return ("🔒 " if m.get("private") else "") + m["memory"]


def labelled(m: dict) -> str:
    return f"{ICONS.get(m.get('type'), '💜')} {visible(m)}"


def waiting_on(names: list[str], done_text: str, waiting_text: str) -> None:
    if names:
        st.caption(f"⏳ {waiting_text}: **{', '.join(names)}**")
    else:
        st.caption(f"✅ {done_text}")


def make_plan() -> None:
    """Build the itinerary for the chosen destination from everything the group has said."""
    if trip.get("plan_runs", 0) >= MAX_PLANS:
        flash(f"This trip has reached its limit of {MAX_PLANS} plans.")
        return
    trip["plan"] = planner.plan_trip(trip["chosen"]["destination"], int(trip["days"]), members, memories)
    trip["memories_used"], trip["plan_runs"] = len(memories), trip.get("plan_runs", 0) + 1
    save_trip()


def choose(prop: dict) -> None:
    trip["chosen"] = prop
    with st.spinner(f"Planning {prop['destination']} around everyone's input..."):
        make_plan()
    ss["goto_tab"] = T_TRIP
    flash(f"{prop['destination']} it is!")
    st.rerun()


def toggle_packed(trip_id: str, item_id: str) -> None:
    current = next((t for t in trips_db.list(BUCKET) if t["id"] == trip_id), None)
    for item in current["packing"] if current else []:
        if item["id"] == item_id:
            item["done"] = bool(ss.get(f"pk_{item_id}"))
            trips_db.save(BUCKET, current)

# ---------------------------------------------------------------------------
# Header: the trip, where the group is, what to do next
# ---------------------------------------------------------------------------

kicker = f"{trip['name']} · {style.count(int(trip['days']), 'day')}" + (f" · from {trip['origin']}" if trip.get("origin") else "")
st.markdown(style.hero([("Travelers", len(members)), ("Notes", len(notes)), ("To pack", len(trip["packing"]))], kicker),
            unsafe_allow_html=True)

journey = [
    ("Everyone's input", "Places, food, travel style, ideas", bool(notes)),
    ("Get proposals", "5-6 trips that fit the group", bool(trip["proposals"])),
    ("Pick a destination", "Vote, then choose together", bool(trip["chosen"])),
    ("Map and plan", "Google Map, itinerary, packing", bool(trip["plan"])),
]
st.markdown(style.steps(journey), unsafe_allow_html=True)

# (message, button label, tab the button opens)
NEXT = [
    ("Pick who's adding, then say where you'd love to go, what you eat and how you like to travel.", None, None),
    ("Input is coming in" + (f" (still waiting on {', '.join(no_input_yet)})" if no_input_yet else " from everyone")
     + ". Ask WanderFolk for trip proposals whenever you're ready.", "Get proposals →", T_PROPS),
    ("Proposals are ready. Vote for the ones you'd go on, then choose one together.", "See proposals →", T_PROPS),
    ("Destination chosen. Build the plan to see the map and itinerary.", "Open our trip →", T_TRIP),
]
step_now = next((i for i, (_, _, done) in enumerate(journey) if not done), None)
msg_col, btn_col = st.columns([4, 1], vertical_alignment="center")
if step_now is None:
    msg_col.markdown(style.next_step(f"You're going to {trip['chosen']['destination']}. The map, itinerary and "
                                     "packing list are ready.", "All set"), unsafe_allow_html=True)
    btn_col.button("Open our trip →", type="primary", width="stretch", on_click=goto, args=(T_TRIP,))
else:
    message, label, target = NEXT[step_now]
    msg_col.markdown(style.next_step(message), unsafe_allow_html=True)
    if target:
        btn_col.button(label, type="primary", width="stretch", on_click=goto, args=(target,))

me_key = f"me_{trip['id']}"
if ss.get(me_key) not in members:
    ss.pop(me_key, None)
me = st.pills("Who's adding right now?", members, default=members[0], key=me_key) or members[0]

tab_input, tab_pack, tab_props, tab_trip, tab_after, tab_memory = st.tabs(
    [T_INPUT, T_PACK, T_PROPS, T_TRIP, T_AFTER, T_MEMORY], key="tab", on_change="rerun")

# ---------------------------------------------------------------------------
# 1. Everyone's input
# ---------------------------------------------------------------------------

with tab_input:
    st.subheader(f"{me}, what would make this trip great?")
    st.caption("Fill in as many or as few as you like. Food needs and travel style are remembered for your next trips too.")
    with st.form(f"input_{me}", clear_on_submit=True, border=False):
        left, right = st.columns(2)
        answers = {}
        for i, (kind, (icon, question, example)) in enumerate(CATEGORIES.items()):
            answers[kind] = (left if i % 2 == 0 else right).text_input(f"{icon} {question}", placeholder=example)
        private = st.checkbox("🔒 Keep what I'm adding now private",
                              help="WanderFolk still plans around it, but the rest of the group never sees "
                                   "the note or who wrote it. Handy for budget.")
        if st.form_submit_button(f"Save for {me}", type="primary"):
            filled = {kind: text.strip() for kind, text in answers.items() if text.strip()}
            if not filled:
                st.warning("Fill in at least one box first.")
            elif all([remember(me, text, kind, private) for kind, text in filled.items()]):
                flash(f"Saved {style.count(len(filled), 'note')} for {me}")
                st.rerun()

    mine = [m for m in memories if m["traveler"] == me]
    if mine:
        with st.expander(f"What WanderFolk knows about {me} · {len(mine)}"):
            for m in mine:
                with st.container(horizontal=True, vertical_alignment="center", wrap=False):
                    st.markdown(labelled(m) + (f"  \n:gray[remembered from {m['trip_name']}]"
                                               if m.get("trip_id") != trip["id"] and m.get("trip_name") else ""))
                    if st.button("🗑️", key=f"del_{m['id']}", help="Delete this", width="content"):
                        forget(m["id"])
                        flash("Deleted")
                        st.rerun()

    st.markdown("#### Everyone so far")
    st.markdown(style.members([
        style.member_card(p, i, [labelled(m) for m in memories if m["traveler"] == p],
                          is_me=p == me, waiting="Hasn't added anything yet")
        for i, p in enumerate(members)]), unsafe_allow_html=True)
    st.markdown(style.hood("each person has their own memory in Mem0, scoped by <code>user_id</code>."),
                unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. Packing list: everyone brainstorms, nobody forgets
# ---------------------------------------------------------------------------

with tab_pack:
    st.subheader("What do we need to bring?")
    st.caption("Everyone adds whatever comes to mind. Tick things off as they get packed.")
    with st.form("pack_form", clear_on_submit=True, border=False):
        a, b = st.columns([5, 1], vertical_alignment="bottom")
        items_in = a.text_input(f"{me} suggests", placeholder="e.g. Sunscreen, first-aid kit, speaker")
        if b.form_submit_button("Add", type="primary", width="stretch"):
            have = {i["text"].lower() for i in trip["packing"]}
            fresh = [t for t in parse_names(items_in) if t.lower() not in have]
            if not fresh:
                st.warning("Type something new first.")
            else:
                trip["packing"] += [{"id": uuid.uuid4().hex[:8], "text": t, "by": me, "done": False} for t in fresh]
                save_trip()
                flash(f"Added {style.count(len(fresh), 'item')}")
                st.rerun()

    suggested = [s for s in ((trip["plan"] or {}).get("packing") or [])
                 if s.lower() not in {i["text"].lower() for i in trip["packing"]}]
    if suggested:
        st.markdown("**WanderFolk suggests for this trip**" + style.chips(suggested), unsafe_allow_html=True)
        if st.button("Add WanderFolk's suggestions to the list"):
            trip["packing"] += [{"id": uuid.uuid4().hex[:8], "text": t, "by": "WanderFolk", "done": False} for t in suggested]
            save_trip()
            st.rerun()

    if trip["packing"]:
        packed = sum(i["done"] for i in trip["packing"])
        st.progress(packed / len(trip["packing"]), text=f"{packed} of {len(trip['packing'])} packed")
        for item in trip["packing"]:
            with st.container(horizontal=True, vertical_alignment="center", wrap=False):
                st.checkbox(f"{item['text']} · :gray[{item['by']}]", value=item["done"], key=f"pk_{item['id']}",
                            on_change=toggle_packed, args=(trip["id"], item["id"]), width="stretch")
                if st.button("🗑️", key=f"pkdel_{item['id']}", help="Remove from the list", width="content"):
                    trip["packing"] = [i for i in trip["packing"] if i["id"] != item["id"]]
                    save_trip()
                    st.rerun()
    else:
        st.markdown(style.empty("Nothing on the list yet. Add the first thing above."), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 3. Proposals: where could we go?
# ---------------------------------------------------------------------------

with tab_props:
    st.subheader("Where could we go?")
    st.caption("WanderFolk reads everyone's input and suggests trips that fit the whole group.")
    waiting_on(no_input_yet, "Everyone has added their input.", "No input yet from")
    if st.button("✨ Suggest trips for us" if not trip["proposals"] else "✨ Suggest again with the latest input",
                 type="primary", disabled=trip.get("suggest_runs", 0) >= MAX_SUGGESTS,
                 help=f"Up to {MAX_SUGGESTS} rounds of proposals per trip."):
        with st.spinner("Reading everyone's input and looking for places that fit..."):
            found, engine = planner.propose_trips(trip.get("origin", ""), int(trip["days"]), members, memories)
        trip.update(proposals=[{"id": uuid.uuid4().hex[:8], **p} for p in found], votes={}, proposals_engine=engine,
                    suggest_runs=trip.get("suggest_runs", 0) + 1)
        save_trip()
        flash(f"{style.count(len(found), 'proposal')} ready")
        st.rerun()

    if trip["proposals"]:
        if trip.get("proposals_engine") == "rules":
            st.info("No AI model is connected, so these come from a small built-in list of places.")
        votes = trip["votes"]
        most = max((len(v) for v in votes.values()), default=0)
        columns = st.columns(2)
        for i, prop in enumerate(trip["proposals"]):
            voters = [p for p in votes.get(prop["id"], []) if p in members]
            with columns[i % 2].container(border=True):
                st.markdown(style.proposal(i + 1, prop, voters, leading=bool(voters) and len(voters) == most),
                            unsafe_allow_html=True)
                with st.container(horizontal=True, vertical_alignment="center"):
                    voted = me in voters
                    if st.button("👎 Remove my vote" if voted else f"👍 {me} would go", key=f"vote_{prop['id']}"):
                        votes[prop["id"]] = [p for p in voters if p != me] if voted else voters + [me]
                        save_trip()
                        st.rerun()
                    st.link_button("🗺️ Google Maps", maps_search(prop["destination"]))
                    if st.button("✅ Choose this", key=f"choose_{prop['id']}", type="primary"):
                        choose(prop)
    else:
        st.markdown(style.empty("Proposals will appear here: 5-6 places, why each fits your group, and what to watch out for."),
                    unsafe_allow_html=True)

    with st.form("own_destination", border=False):
        a, b = st.columns([5, 1], vertical_alignment="bottom")
        own = a.text_input("Already know where you're going?", placeholder="e.g. Lake Tahoe")
        if b.form_submit_button("Choose it", width="stretch"):
            if own.strip():
                choose({"id": "own", "destination": own.strip(), "tagline": "The group's own pick", "why": [],
                        "watch_out": "", "travel": "", "budget": "", "highlights": []})
            else:
                st.warning("Type a destination first.")

# ---------------------------------------------------------------------------
# 4. Our trip: the map, the itinerary and why
# ---------------------------------------------------------------------------

with tab_trip:
    if not trip["chosen"]:
        st.subheader("Our trip")
        st.markdown(style.empty("Choose a destination in Proposals and the Google Map and itinerary will appear here."),
                    unsafe_allow_html=True)
    else:
        place = trip["chosen"]["destination"]
        st.subheader(f"📍 {place}")
        if trip["chosen"].get("tagline"):
            st.caption(trip["chosen"]["tagline"])
        st.iframe(f"https://www.google.com/maps?q={quote_plus(place)}&output=embed", height=380)
        with st.container(horizontal=True, vertical_alignment="center"):
            st.link_button("🗺️ Open in Google Maps", maps_search(place))
            if trip.get("origin"):
                st.link_button(f"🚗 Directions from {trip['origin']}",
                               "https://www.google.com/maps/dir/?api=1"
                               f"&origin={quote_plus(trip['origin'])}&destination={quote_plus(place)}")
            if st.button("🔄 Re-plan with the latest input"):
                with st.spinner("Planning..."):
                    make_plan()
                flash("Plan updated")
                st.rerun()
        if trip["plan"]:
            left, right = st.columns([3, 2], gap="large")
            with left:
                st.markdown(style.plan_head("The itinerary"), unsafe_allow_html=True)
                st.markdown("".join(style.day_card(day) for day in trip["plan"]["days"]), unsafe_allow_html=True)
            with right:
                st.markdown(style.plan_head("🧠 Why the plan looks like this"), unsafe_allow_html=True)
                changes = trip["plan"].get("changes", [])
                if changes:
                    st.markdown("".join(style.why_card(c) for c in changes), unsafe_allow_html=True)
                else:
                    st.markdown(style.empty("No notes shaped this plan yet."), unsafe_allow_html=True)
                if trip["plan"].get("redactions"):
                    st.caption(f"🛡️ Privacy guard removed {style.count(trip['plan']['redactions'], 'leak')} of private notes.")
                st.markdown(style.hood(f"used {trip.get('memories_used', 0)} memories · {scope_label} · planner: "
                                       f"{'AI' if trip['plan'].get('engine') == 'ai' else 'offline rules'}"),
                            unsafe_allow_html=True)
        st.caption("Changed your minds? Choose a different place in Proposals.")

# ---------------------------------------------------------------------------
# 5. After the trip
# ---------------------------------------------------------------------------

with tab_after:
    st.subheader(f"How did it go, {me}?")
    st.caption("What worked? What didn't? WanderFolk remembers this for your next trip, "
               "so the same mistake doesn't happen twice.")
    with st.form(f"fb_{me}", clear_on_submit=True, border=False):
        fb = st.text_area(f"{me}'s feedback", height=90, placeholder="e.g. The 7am start was too early")
        if st.form_submit_button("Add feedback", type="primary"):
            if not fb.strip():
                st.warning("Type something first.")
            elif remember(me, fb.strip(), "feedback"):
                flash(f"Feedback saved for {me}")
                st.rerun()
    said = [m for m in memories if m.get("type") == "feedback" and m.get("trip_id") == trip["id"]]
    if said:
        st.markdown("**What the group said about this trip**"
                    + style.chips([f"{m['traveler']}: {visible(m)}" for m in said]), unsafe_allow_html=True)
    st.markdown(style.hood(f"feedback goes to this trip's shared memory in Mem0, <code>run_id={trip['id']}</code>."),
                unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 6. Memory
# ---------------------------------------------------------------------------

with tab_memory:
    st.subheader("What WanderFolk remembers")
    st.caption(f"Viewing as **{me}**. Private notes stay hidden from everyone except their owner.")
    with st.form("search_form", border=False):
        a, b = st.columns([5, 1], vertical_alignment="bottom")
        q = a.text_input("Ask about the group in plain words", value="Who has food or dietary needs?")
        asked = b.form_submit_button("Search", width="stretch")
    if asked:
        try:
            hits = [m for m in store.search(q, user_ids=people_ids) if m.get("group") == crew and m.get("traveler") in members]
        except Exception as e:
            hits = []
            st.warning(f"Search failed: {e}")
        if hits:
            st.markdown(style.chips([f"{m['traveler']}: {visible(m)}" for m in hits]), unsafe_allow_html=True)
        else:
            st.caption("No matches.")
    st.markdown(style.hood(f"one search across every traveler · {scope_label}"), unsafe_allow_html=True)

    for person in members:
        theirs = [m for m in memories if m["traveler"] == person]
        with st.expander(f"{person} · {len(theirs)} saved"):
            for m in theirs:
                with st.container(horizontal=True, vertical_alignment="center", wrap=False):
                    st.markdown(labelled(m))
                    if (person == me or not m.get("private")) and st.button("🗑️", key=f"mdel_{m['id']}",
                                                                           help="Delete this memory", width="content"):
                        forget(m["id"])
                        flash("Memory deleted")
                        st.rerun()
            if not theirs:
                st.caption("Nothing saved yet.")
