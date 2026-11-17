"""
WanderFolk planner: turns the group's memories into an itinerary, and says WHICH memory caused each choice.

plan_trip() tries the AI model first and falls back to a rule-based planner, so the demo always works.
No Streamlit here, so it is easy to test.
"""

from __future__ import annotations

import re

import llm

# ---------------------------------------------------------------------------
# Demo data (fake people)
# ---------------------------------------------------------------------------

DEMO_TRAVELERS = ["Priya", "Arjun", "Maya"]

# Preferences people state up front. The problems (early starts, driving, sunburn) are things nobody
# thinks to mention until a trip goes wrong, which is exactly what the feedback memory is for.
DEMO_PREFERENCES = [
    ("Priya", "I love hiking and being outdoors", False),
    ("Arjun", "I'm vegetarian", False),
    ("Maya", "I love the beach", False),
    ("Maya", "My budget is about $100 a day, please don't tell the group", True),
]

DEMO_FEEDBACK = [
    ("Priya", "The 7am hike was way too early, I was exhausted all day"),
    ("Arjun", "Loved the taco place by the beach, more spots like that please"),
    ("Maya", "Too much driving between towns, I felt sick in the car"),
    ("Maya", "We forgot sunscreen and everyone got burned"),
]

# Said before trip 2: a new need nobody had on trip 1.
DEMO_NEW_NEED = ("Arjun", "My dad is joining this time and he uses a wheelchair", False)

# Community tips: left by OTHER groups who visited. Shared across every WanderFolk user.
DEMO_COMMUNITY = {
    "Big Sur": [
        "The McWay Falls overlook is a short, paved, wheelchair-friendly path with an amazing view",
        "Pfeiffer Beach has a steep sandy path, not good for wheelchairs",
        "Bixby Bridge pull-out parking is full by 10am on weekends, go after 3pm",
    ],
    "Santa Cruz": [
        "West Cliff Drive has a flat paved path along the ocean, great for everyone",
    ],
}

# ---------------------------------------------------------------------------
# Rule-based understanding of memories (used offline, and to double-check the AI)
# ---------------------------------------------------------------------------

RULES = [
    # key, pattern, what the planner does about it
    ("late_start", r"\b(not a morning person|hate early|too early|early start|sleep in|7 ?am)\b",
     "Start each day at 10:00 AM or later"),
    ("hiking", r"\b(hik\w*|trail|outdoors?|nature)\b", "Include a scenic hike"),
    ("vegetarian", r"\b(vegetarian|vegan|no meat)\b", "Pick vegetarian-friendly places for every meal"),
    ("local_food", r"\b(local food|taco|street food|food spots?|hole[- ]in[- ]the[- ]wall|loved the \w+ (place|spot))\b",
     "Add a casual local food stop"),
    ("relaxed", r"\b(relaxed|slow|not too many|chill|downtime)\b", "Keep it to 3 activities a day with downtime"),
    ("less_driving", r"\b(carsick|car sick|too much driving|long drives?|windy roads?|windy drives?)\b",
     "Stay in one base town and keep drives under 30 minutes"),
    ("budget", r"(\$\s?\d+|\bbudget\b|\bcheap\b|\bafford\b|\bexpensive\b)", "Favor free or low-cost activities"),
    ("sunscreen", r"\b(sunscreen|sunburn|burned|burnt)\b", "Add sunscreen to the packing list"),
    ("beach", r"\b(beach|ocean|surf)\b", "Include beach time"),
    ("accessible", r"\b(wheelchair|mobility|walker|can'?t do stairs|cannot do stairs|step-free)\b",
     "Choose step-free, wheelchair-friendly stops"),
]


def detect(text: str) -> list[str]:
    return [key for key, pat, _ in RULES if re.search(pat, text, re.I)]


RULE_ACTION = {key: action for key, _, action in RULES}


def adaptations(memories: list[dict]) -> list[dict]:
    """
    Which planning rules do the group's memories trigger, and which memory is the reason for each?
    Problems are best explained by what happened on a trip (feedback); likes by what people said (preferences).
    Returns [{"key", "action", "because", "who", "private", "kind", "trip"}], one per rule.
    """
    feedback_first = {"late_start", "less_driving", "sunscreen", "local_food", "relaxed"}
    own = [m for m in memories if m.get("type") != "community"]  # other groups' tips don't set OUR preferences
    changes = []
    for key in RULE_ACTION:
        candidates = [m for m in own if key in detect(m["memory"])]
        if not candidates:
            continue
        prefer = "feedback" if key in feedback_first else "preference"
        m = sorted(candidates, key=lambda m: 0 if m.get("type") == prefer else 1)[0]
        changes.append({"key": key, "action": RULE_ACTION[key], "because": m["memory"],
                        "who": m.get("traveler_name") or m.get("traveler") or "someone",
                        "private": bool(m.get("private")), "kind": m.get("type", "preference"),
                        "trip": m.get("trip_name", "")})
    return changes

GOOD = r"\b(paved|flat|wheelchair[- ]friendly|accessible|step-free|great for everyone)\b"
BAD = r"\b(steep|stairs|not good for|closed|avoid|dangerous)\b"
HEADS_UP = r"\b(parking|crowded|full by|go after|go before|reservation)\b"


def place_of(note: str) -> str:
    """'The McWay Falls overlook is a short...' -> 'McWay Falls overlook'"""
    m = re.match(r"(?:the\s+)?(.+?)\s+(?:is|has|was|are|have|gets|parking)\b", note, re.I)
    return (m.group(1) if m else note[:40]).strip().rstrip(",")


def community_changes(community: list[dict], keys: set[str]) -> list[dict]:
    """How tips from other travelers shape this plan."""
    out = []
    for m in community:
        note = m["memory"]
        base = {"because": note, "who": "another traveler", "private": False, "kind": "community", "trip": ""}
        if re.search(BAD, note, re.I) and ("accessible" in keys or re.search(r"closed|dangerous", note, re.I)):
            out.append({**base, "key": "avoid", "action": f"Skipped {place_of(note)}"})
        elif re.search(GOOD, note, re.I):
            out.append({**base, "key": "include", "action": f"Added {place_of(note)}"})
        elif re.search(HEADS_UP, note, re.I):
            out.append({**base, "key": "timing", "action": f"Timed the {place_of(note)} stop around the crowds"})
    return out

def time_key(t: str) -> int:
    """'4:30 PM' -> minutes since midnight, for sorting. Unknown formats go last."""
    m = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap]m)", t or "", re.I)
    if not m:
        return 24 * 60
    h, mins, ap = int(m.group(1)) % 12, int(m.group(2) or 0), m.group(3).lower()
    return (h + (12 if ap == "pm" else 0)) * 60 + mins


def sort_days(plan: dict) -> dict:
    for d in plan.get("days", []):
        d["items"] = sorted(d.get("items", []), key=lambda i: time_key(i.get("time", "")))
    return plan

# ---------------------------------------------------------------------------
# Offline planner
# ---------------------------------------------------------------------------


def _offline_days(destination: str, days: int, keys: set[str], tips: list[dict] | None = None) -> list[dict]:
    start = "10:00 AM" if "late_start" in keys else "6:30 AM"
    hike_time = "10:30 AM" if "late_start" in keys else "7:00 AM"
    veg = " (great vegetarian options)" if "vegetarian" in keys else ""
    cheap = "budget" in keys
    one_base = "less_driving" in keys

    plan = []
    for d in range(1, days + 1):
        items = []
        if d == 1:
            items.append({"time": start, "activity": f"Arrive in {destination} and check in" + (" (one base for the whole trip)" if one_base else "")})
            if "hiking" in keys:
                hike = (f"Paved, step-free scenic walk near {destination}" if "accessible" in keys
                        else f"Scenic coastal hike near {destination}")
                items.append({"time": hike_time, "activity": hike})
        else:
            if not one_base:
                items.append({"time": start, "activity": "Drive to a neighboring town (about 1 hour)"})
            if "beach" in keys or d == 2:
                items.append({"time": "11:00 AM" if "late_start" in keys else "9:00 AM",
                              "activity": ("Accessible beach overlook" if "accessible" in keys
                                           else f"{'Free ' if cheap else ''}beach time and tide pools")})
        for t in (tips or []):
            if t["key"] == "include" and t.get("day", 1) == d:
                items.append({"time": "4:30 PM", "activity": f"Visit {place_of(t['because'])} (tip from another traveler)"})
            if t["key"] == "timing" and d == 1:
                items.append({"time": "3:30 PM", "activity": f"Stop at {place_of(t['because'])} after the morning rush"})
        items.append({"time": "1:00 PM", "activity": (f"Lunch at a casual local food spot{veg}" if "local_food" in keys
                                                       else f"Lunch at a popular sit-down restaurant{veg}")})
        if "relaxed" not in keys:
            items.append({"time": "3:00 PM", "activity": "Guided tour" + (" (free walking tour)" if cheap else "")})
            items.append({"time": "5:00 PM", "activity": "Shopping on the main street"})
        else:
            items.append({"time": "3:30 PM", "activity": "Downtime: café or nap"})
        items.append({"time": "7:00 PM", "activity": ("Picnic dinner at sunset" if cheap else
                                                       "Dinner at a well-reviewed restaurant") + veg})
        plan.append({"day": d, "items": items})
    return plan


def offline_plan(destination: str, days: int, memories: list[dict]) -> dict:
    changes = adaptations(memories)
    keys = {c["key"] for c in changes}
    tips = community_changes([m for m in memories if m.get("type") == "community"], keys)
    changes += tips
    packing = ["Comfortable shoes", "Water bottle", "Layers for the evening"]
    if "sunscreen" in keys:
        packing.insert(0, "Sunscreen (everyone!)")
    if "less_driving" in keys:
        packing.append("Motion-sickness tablets")

    return {"title": f"{days}-day trip to {destination}", "days": _offline_days(destination, days, keys, tips),
            "changes": changes, "packing": packing, "engine": "rules"}

# ---------------------------------------------------------------------------
# AI planner
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """You are WanderFolk, a group trip planner.
Plan the trip using the group's memories. Every important choice must come from a memory, and you must cite it.
Rules:
- Memories marked PRIVATE: respect them silently. Never mention the person, the amount, or the reason in the itinerary.
  In "changes", set "private": true and write "because" as "a private preference" with "who": "private".
- Feedback from past trips matters most: it describes what actually went wrong or right.
- "community" memories are tips from OTHER travelers who visited this place. Use them to pick or skip specific
  places (especially for accessibility), and cite them with "who": "another traveler", "kind": "community".
- Be concrete: real-sounding places and times for the destination. Keep it realistic for the travel time.
Return JSON: {"title": str,
 "days": [{"day": int, "items": [{"time": "10:30 AM", "activity": str}]}],
 "changes": [{"action": "<what you did, max 12 words>", "because": "<the memory, quoted or paraphrased>",
              "who": "<traveler name or 'private'>", "private": bool, "kind": "feedback" | "preference" | "community",
              "trip": "<past trip name if feedback, else ''>"}],
 "packing": [str]}"""


def _memory_lines(memories: list[dict]) -> str:
    lines = []
    for m in memories:
        who = m.get("traveler_name") or m.get("traveler") or "someone"
        tag = "PRIVATE " if m.get("private") else ""
        where = f" (feedback after {m['trip_name']})" if m.get("type") == "feedback" and m.get("trip_name") else ""
        if m.get("type") == "community":
            who = "another traveler"
        lines.append(f"- {tag}{m.get('type', 'preference')} from {who}{where}: {m['memory']}")
    return "\n".join(lines) or "- (no memories yet)"


def ai_plan(destination: str, days: int, travelers: list[str], memories: list[dict],
            previous: dict | None) -> dict | None:
    prev = ""
    if previous:
        prev = "\nPrevious trip itinerary (" + previous["name"] + "): " + "; ".join(
            f"Day {d['day']}: " + ", ".join(f"{i['time']} {i['activity']}" for i in d["items"])
            for d in previous["plan"]["days"])
    result = llm.ask_json(PLANNER_PROMPT,
                          f"Destination: {destination}\nDays: {days}\nTravelers: {', '.join(travelers)}\n"
                          f"Group memories:\n{_memory_lines(memories)}{prev}", max_tokens=4000)
    if not result or not isinstance(result.get("days"), list) or not result["days"]:
        return None
    result.setdefault("changes", [])
    result.setdefault("packing", [])
    result["engine"] = "ai"
    return result

# ---------------------------------------------------------------------------
# Trip proposals: before there is a destination, suggest a handful for the group to choose from
# ---------------------------------------------------------------------------

PROPOSAL_PROMPT = """You are WanderFolk, a travel planner for a group of friends who have not picked a destination yet.
Suggest {n} trip destinations for this group, anywhere in the United States: all 50 states, Washington DC and
Puerto Rico, from big cities to small towns and national parks. Don't default to places near the start city or to
California. Spread the options across different parts of the country (West Coast, Southwest, Mountain West, Midwest,
South, Northeast, Alaska, Hawaii), with no more than two from the same state, unless the group asked to stay close
or to drive. Keep each one realistic for the trip length: for 1 to 2 days, favor places a short flight or drive
away; for longer trips, anywhere works. If someone named a place outside the US, suggest the closest US match.
Use what each member told you: places they would love, food and dietary needs, how they like to travel, their own
ideas for this trip, and feedback from past trips. If members named specific places, include the ones that fit.
Make the options clearly different from each other, and be honest about trade-offs.
Notes marked PRIVATE: use them to choose, but never quote them, never mention money amounts from them, and never
say whose they are.
JSON shape:
{{"proposals": [{{"destination": "<city, town or park>, <full state name>", "tagline": "<max 10 words>",
  "why": ["<a reason this fits, naming the member it comes from, max 20 words>"],
  "watch_out": "<one honest trade-off for this group, or ''>",
  "travel": "<drive or fly, and rough travel time from the start city>", "budget": "<$, $$ or $$$>",
  "highlights": ["<short thing to do>", "<short thing to do>", "<short thing to do>"]}}]}}
Give 2 to 4 reasons per destination."""

# Used when no AI model is configured: (destination, region, tagline, what it suits, budget, highlights).
# Covers the whole country so offline suggestions aren't stuck near one coast.
OFFLINE_DESTINATIONS = [
    # West Coast
    ("Lake Tahoe, California", "West Coast", "Alpine lake, trails and cabins", r"lake|hik|mountain|cabin|snow|ski|swim|nature|outdoor",
     "$$", ["Emerald Bay viewpoint", "Lakeside beach day", "Sunset hike"]),
    ("Big Sur, California", "West Coast", "Dramatic coast and redwoods", r"coast|ocean|hik|scenic|camp|nature|view|outdoor",
     "$$", ["McWay Falls overlook", "Bixby Bridge", "Redwood trail"]),
    ("San Diego, California", "West Coast", "Sunny beaches and great food", r"beach|city|food|taco|zoo|warm|sun|museum",
     "$$", ["La Jolla Cove", "Balboa Park", "Old Town tacos"]),
    ("Portland, Oregon", "West Coast", "Food carts, coffee and forest walks", r"city|food|vegetarian|vegan|coffee|beer|art|rain",
     "$$", ["Food cart pods", "Forest Park trail", "Powell's Books"]),
    ("Seattle, Washington", "West Coast", "Markets, ferries and mountain views", r"city|food|coffee|seafood|ferry|island|music|rain",
     "$$", ["Pike Place Market", "Ferry to Bainbridge Island", "Kerry Park at sunset"]),
    ("Olympic National Park, Washington", "West Coast", "Rainforest, glaciers and wild beaches", r"forest|rainforest|hik|beach|camp|nature|wild|outdoor",
     "$$", ["Hoh Rain Forest", "Hurricane Ridge", "Ruby Beach"]),
    # Southwest
    ("Grand Canyon, Arizona", "Southwest", "The big canyon, rim to river", r"canyon|hik|view|desert|camp|photo|nature|outdoor",
     "$$", ["South Rim sunrise", "Bright Angel Trail", "Desert View Watchtower"]),
    ("Sedona, Arizona", "Southwest", "Red rocks, trails and spas", r"desert|hik|spa|relax|red rock|yoga|view|star",
     "$$$", ["Cathedral Rock trail", "Jeep tour", "Stargazing"]),
    ("Santa Fe, New Mexico", "Southwest", "Adobe streets, art and green chile", r"art|food|history|culture|museum|spicy|chile|slow",
     "$$", ["Canyon Road galleries", "Meow Wolf", "Green chile everything"]),
    ("Las Vegas, Nevada", "Southwest", "Shows, food and desert day trips", r"party|nightlife|show|casino|city|food|fun|birthday|bachelor",
     "$$", ["A big show", "Red Rock Canyon", "Late-night food crawl"]),
    ("Zion National Park, Utah", "Southwest", "Slot canyons and red cliffs", r"canyon|hik|climb|river|desert|camp|nature|outdoor|adventure",
     "$$", ["The Narrows", "Canyon Overlook Trail", "Springdale dinner"]),
    ("Moab, Utah", "Southwest", "Arches, mountain bikes and big skies", r"arch|bike|desert|hik|adventure|star|camp|offroad|jeep",
     "$$", ["Delicate Arch", "Mountain biking", "Dead Horse Point sunset"]),
    # Mountain West
    ("Denver and the Rockies, Colorado", "Mountain West", "City base with mountains next door", r"mountain|hik|beer|city|ski|snow|outdoor|music",
     "$$", ["Red Rocks Amphitheatre", "Day trip to Rocky Mountain National Park", "Brewery crawl"]),
    ("Aspen, Colorado", "Mountain West", "Snowy peaks and a pretty mountain town", r"ski|snow|mountain|luxury|spa|hik|winter|cabin",
     "$$$", ["Maroon Bells", "Ski or snowshoe", "Après in town"]),
    ("Yellowstone National Park, Wyoming", "Mountain West", "Geysers, wildlife and wide valleys", r"wildlife|geyser|nature|hik|camp|photo|animals|outdoor",
     "$$", ["Old Faithful", "Grand Prismatic Spring", "Lamar Valley wildlife"]),
    ("Jackson Hole, Wyoming", "Mountain West", "Teton views and a cowboy town", r"mountain|ski|snow|hik|wildlife|western|cowboy|view",
     "$$$", ["Grand Teton viewpoints", "Jenny Lake", "Town Square"]),
    ("Glacier National Park, Montana", "Mountain West", "Glacial lakes and alpine roads", r"lake|glacier|hik|mountain|scenic|camp|nature|outdoor",
     "$$", ["Going-to-the-Sun Road", "Lake McDonald", "Hidden Lake trail"]),
    ("Boise, Idaho", "Mountain West", "Easygoing city with rivers and hot springs", r"river|hot spring|relax|budget|cheap|float|outdoor|quiet",
     "$", ["Float the Boise River", "Hot springs day trip", "Basque Block food"]),
    # Midwest
    ("Chicago, Illinois", "Midwest", "Architecture, lakefront and deep dish", r"city|food|museum|architecture|music|art|nightlife|pizza",
     "$$", ["Architecture river cruise", "Lakefront bike ride", "Deep dish pizza"]),
    ("Door County, Wisconsin", "Midwest", "Lake towns, cherries and fish boils", r"lake|relax|slow|cabin|bike|quiet|cherry|cheese",
     "$$", ["Peninsula State Park", "Fish boil dinner", "Cave Point kayaking"]),
    ("Traverse City, Michigan", "Midwest", "Dunes, beaches and wineries", r"lake|beach|wine|dune|relax|summer|food",
     "$$", ["Sleeping Bear Dunes", "Old Mission wineries", "Cherry pie"]),
    ("Minneapolis, Minnesota", "Midwest", "Lakes in the city and a big music scene", r"lake|city|music|bike|art|food|budget",
     "$", ["Chain of Lakes", "First Avenue show", "Mill City Museum"]),
    ("Kansas City, Missouri", "Midwest", "Barbecue and jazz", r"food|bbq|barbecue|jazz|music|city|budget|cheap",
     "$", ["Barbecue crawl", "18th and Vine jazz", "Nelson-Atkins Museum"]),
    # South
    ("New Orleans, Louisiana", "South", "Music, food and late nights", r"music|jazz|food|party|nightlife|history|culture|city",
     "$$", ["French Quarter walk", "Frenchmen Street jazz", "Beignets"]),
    ("Nashville, Tennessee", "South", "Live music on every corner", r"music|country|party|nightlife|food|bachelor|birthday|city",
     "$$", ["Broadway honky-tonks", "Grand Ole Opry", "Hot chicken"]),
    ("Great Smoky Mountains, Tennessee", "South", "Misty ridges and cabins", r"mountain|hik|cabin|waterfall|nature|camp|budget|outdoor",
     "$", ["Clingmans Dome", "Laurel Falls", "Cabin nights"]),
    ("Asheville, North Carolina", "South", "Blue Ridge views and craft beer", r"mountain|beer|art|food|hik|relax|vegetarian|vegan",
     "$$", ["Blue Ridge Parkway", "River Arts District", "Brewery hop"]),
    ("Charleston, South Carolina", "South", "Historic streets and Lowcountry food", r"history|food|beach|slow|relax|seafood|architecture",
     "$$", ["Rainbow Row", "Folly Beach", "Shrimp and grits"]),
    ("Savannah, Georgia", "South", "Squares, oaks and slow walks", r"history|slow|walk|food|ghost|relax|architecture",
     "$$", ["Forsyth Park", "Historic squares walk", "Ghost tour"]),
    ("Miami, Florida", "South", "Beaches, Cuban food and nightlife", r"beach|nightlife|party|food|art|warm|sun|city",
     "$$$", ["South Beach", "Little Havana", "Wynwood Walls"]),
    ("Florida Keys, Florida", "South", "Island hopping and clear water", r"beach|island|snorkel|boat|relax|warm|sun|fish",
     "$$$", ["Snorkel at Bahia Honda", "Key West sunset", "Seven Mile Bridge"]),
    ("Austin, Texas", "South", "Live music, tacos and swimming holes", r"music|taco|food|bbq|swim|city|nightlife|budget",
     "$$", ["Barton Springs Pool", "Sixth Street music", "Breakfast tacos"]),
    ("Ozark Mountains, Arkansas", "South", "Lakes, caves and cheap cabins", r"lake|cabin|hik|cave|budget|cheap|float|nature",
     "$", ["Buffalo National River", "Hot Springs", "Lakeside cabin"]),
    # Northeast
    ("New York City, New York", "Northeast", "Everything, all at once", r"city|food|museum|art|show|broadway|nightlife|shopping",
     "$$$", ["A Broadway show", "Central Park", "Food crawl in Queens"]),
    ("Boston, Massachusetts", "Northeast", "History, seafood and walkable streets", r"history|seafood|city|walk|museum|sport|college",
     "$$", ["Freedom Trail", "North End dinner", "Harbor islands"]),
    ("Acadia National Park, Maine", "Northeast", "Rocky coast and lobster rolls", r"coast|hik|lobster|seafood|ocean|nature|camp|bike",
     "$$", ["Cadillac Mountain sunrise", "Jordan Pond", "Lobster rolls in Bar Harbor"]),
    ("Stowe, Vermont", "Northeast", "Snowy hills, maple and cozy inns", r"snow|ski|cozy|cabin|fall|maple|relax|slow|cheese",
     "$$", ["Ski or hike Mount Mansfield", "Maple sugarhouse", "Cheese and cider tasting"]),
    ("Cape Cod, Massachusetts", "Northeast", "Beach towns and dunes", r"beach|seafood|bike|relax|slow|summer|ocean",
     "$$$", ["Cape Cod National Seashore", "Provincetown", "Clam shack lunch"]),
    ("Washington, District of Columbia", "Northeast", "Free museums and monuments", r"museum|history|free|budget|cheap|city|politic|monument",
     "$$", ["Smithsonian museums", "Monuments at night", "Eastern Market"]),
    # Alaska and Hawaii
    ("Anchorage and Kenai Fjords, Alaska", "Alaska", "Glaciers, whales and huge wild country", r"glacier|wildlife|whale|wild|adventure|hik|snow|northern lights",
     "$$$", ["Kenai Fjords boat tour", "Exit Glacier", "Seward harbor"]),
    ("Maui, Hawaii", "Hawaii", "Beaches, waterfalls and a volcano sunrise", r"beach|island|snorkel|surf|warm|relax|waterfall|honeymoon",
     "$$$", ["Haleakalā sunrise", "Road to Hana", "Snorkel at Molokini"]),
    ("Big Island, Hawaii", "Hawaii", "Volcanoes, black sand and stargazing", r"volcano|beach|island|snorkel|star|hik|adventure|warm",
     "$$$", ["Hawaiʻi Volcanoes National Park", "Punaluʻu black sand beach", "Maunakea stars"]),
    ("San Juan, Puerto Rico", "Caribbean", "Old city streets and warm water, no passport needed", r"beach|island|history|food|nightlife|warm|rum|salsa",
     "$$", ["Old San Juan walk", "El Yunque rainforest", "Bioluminescent bay"]),
]


def _named(place: str, memories: list[dict]) -> bool:
    """Did someone name this place (its city/park or its state) in a note?"""
    city, state = [x.strip().lower() for x in (place.split(",") + [""])[:2]]
    words = [w for w in re.split(r"\s+and\s+", city) if len(w) > 3] + ([state] if state else [])
    return any(re.search(rf"\b{re.escape(w)}\b", m["memory"], re.I) for m in memories for w in words)


def offline_proposals(memories: list[dict], n: int = 6) -> list[dict]:
    """Rank the built-in list by what the group said, then spread the picks across the country."""
    scored = []
    for i, (destination, region, tagline, suits, budget, highlights) in enumerate(OFFLINE_DESTINATIONS):
        hits = [m for m in memories if re.search(suits, m["memory"], re.I)]
        why = [f"{m.get('traveler_name') or m.get('traveler') or 'Someone'} said: “{m['memory']}”"
               for m in hits if not m.get("private")][:3]
        score = len(hits) + (3 if _named(destination, memories) else 0)
        scored.append((score, i, region, {"destination": destination, "tagline": tagline, "budget": budget, "travel": "",
                                          "why": why or ["A good all-round pick for a group"], "watch_out": "",
                                          "highlights": highlights}))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picks, regions = [], set()
    for score, _, region, prop in scored:         # first pass: best match from each region
        if region not in regions or (score >= 3 and _named(prop["destination"], memories)):
            picks.append(prop)
            regions.add(region)
        if len(picks) == n:
            return picks
    for _, _, _, prop in scored:                    # then fill with the next best anywhere
        if prop not in picks:
            picks.append(prop)
        if len(picks) == n:
            break
    return picks


def _leaks(text: str, memories: list[dict]) -> bool:
    """Does this text give away a private note (its wording, its amount, or its owner next to a money word)?"""
    t = (text or "").lower()
    markers = _private_markers(memories)
    owners = {m.get("traveler_name") or m.get("traveler") for m in memories if m.get("private")}
    return any(m["memory"].lower() in t for m in memories if m.get("private")) or \
        any(mk.lower() in t for mk in markers if mk.startswith("$")) or \
        (any(o and o.lower() in t for o in owners) and any(mk in t for mk in markers if not mk.startswith("$")))


def propose_trips(origin: str, days: int, travelers: list[str], memories: list[dict], n: int = 6) -> tuple[list[dict], str]:
    """Returns (proposals, 'ai' or 'rules'). Each proposal: destination, tagline, why, watch_out, travel, budget, highlights."""
    result = llm.ask_json(PROPOSAL_PROMPT.format(n=n),
                          f"Start city: {origin or 'not given'}\nTrip length: {days} days\n"
                          f"Travelers ({len(travelers)}): {', '.join(travelers)}\n"
                          f"What the group told you:\n{_memory_lines(memories)}", max_tokens=3000)
    raw = result.get("proposals") if isinstance(result, dict) else None
    proposals = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not str(item.get("destination", "")).strip():
            continue
        text = lambda key: "" if _leaks(str(item.get(key, "")), memories) else str(item.get(key, "")).strip()
        lines = lambda key: [str(x).strip() for x in item.get(key, []) if str(x).strip() and not _leaks(str(x), memories)] \
            if isinstance(item.get(key), list) else []
        proposals.append({"destination": str(item["destination"]).strip(), "tagline": text("tagline"),
                          "why": lines("why"), "watch_out": text("watch_out"), "travel": text("travel"),
                          "budget": text("budget"), "highlights": lines("highlights")})
    if len(proposals) >= 3:
        return proposals[:n], "ai"
    return offline_proposals(memories, n), "rules"

# ---------------------------------------------------------------------------
# Privacy guard: private notes must never show up in what the group sees
# ---------------------------------------------------------------------------


def _private_markers(memories: list[dict]) -> list[str]:
    markers = []
    for m in memories:
        if m.get("private"):
            markers += re.findall(r"\$\s?\d[\d,]*", m["memory"])
            markers += [w for w in ("budget", "afford", "salary", "money") if w in m["memory"].lower()]
    return markers


def privacy_guard(plan: dict, memories: list[dict]) -> tuple[dict, int]:
    """Redact anything that leaks a private note. Returns (plan, number_of_redactions)."""
    markers = _private_markers(memories)
    private_texts = {m["memory"] for m in memories if m.get("private")}
    owners = {m.get("traveler_name") or m.get("traveler") for m in memories if m.get("private")}
    redactions = 0

    def leaks(text: str) -> bool:
        t = (text or "").lower()
        return any(mk.lower() in t for mk in markers if mk.startswith("$")) or \
            (any(o and o.lower() in t for o in owners) and any(mk in t for mk in markers if not mk.startswith("$")))

    for day in plan.get("days", []):
        for item in day.get("items", []):
            if leaks(item.get("activity", "")):
                item["activity"] = re.sub(r"\$\s?\d[\d,]*", "", item["activity"]).strip()
                redactions += 1
    for c in plan.get("changes", []):
        if c.get("private") or c.get("because") in private_texts or leaks(c.get("because", "")):
            if c.get("because") != "a private preference" or c.get("who") != "private":
                redactions += 0 if c.get("private") else 1
            c.update({"private": True, "because": "a private preference", "who": "private"})
    return plan, redactions


def plan_trip(destination: str, days: int, travelers: list[str], memories: list[dict],
              previous: dict | None = None) -> dict:
    plan = ai_plan(destination, days, travelers, memories, previous) or offline_plan(destination, days, memories)
    plan, n = privacy_guard(sort_days(plan), memories)
    plan["redactions"] = n
    return plan
