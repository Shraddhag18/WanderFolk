# 🏔️ WanderFolk

**A project I built at SF Tech Week 2026**, during the /build-with-AI Buildathon (Mem0 × SVAI Hub × The Gen Academy).

WanderFolk is a simple travel planner agent for a group of friends. Everyone says where they'd love to go, what they eat, how they like to travel and what to pack. WanderFolk proposes 5-6 destinations that fit the whole group, the group picks one, and it shows the Google Map, a day-by-day itinerary and the reason behind every choice.

## How it works

1. **Start a trip:** give it a name, a start city, the number of days, and up to 12 people. No destination needed yet.
2. **Everyone's input:** pick who's adding, then fill in any of four boxes: places you'd love, food and dietary needs, how you like to travel, and your own idea for this trip. Anything can be marked private.
3. **Packing list:** everyone brainstorms what to bring and ticks things off as they're packed.
4. **Proposals:** WanderFolk suggests 5-6 destinations, each with why it fits the group, what to watch out for, rough travel time and budget. Vote, then choose one, or type your own.
5. **Our trip:** an embedded Google Map, directions from your start city, an itinerary, and the note behind each choice.
6. **After the trip:** leave feedback, so the next trip avoids the same mistakes.

## What it remembers

WanderFolk keeps what people tell it in [Mem0](https://mem0.ai), so nobody has to repeat themselves.

| What | Where it lives | Example |
|---|---|---|
| Each person's notes | Mem0 `user_id`, one per person | Priya: "Vegetarian" |
| Feedback on a trip | Mem0 `run_id`, one per trip | Priya: "The 7am hike was way too early" |
| Everything the planner knows | Mem0 `agent_id` + `app_id`, across everyone | "Who has food or dietary needs?" |
| Private notes | Mem0 metadata `private: true` | Maya: "Budget about $100 a day" |
| Trips, votes, packing list, itinerary | A local JSON file in `.data/` | |

Dietary needs, travel style and feedback carry over to each person's next trip. Places and ideas belong to one trip only.

Private notes are used for planning but never shown to the group. A privacy guard checks every proposal and itinerary so the wording, the amounts and the owner of a private note don't leak.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

To use Mem0 and Claude, create a file named `.env` next to `app.py` with your own keys:

```
MEM0_API_KEY=your-mem0-key
ANTHROPIC_API_KEY=your-anthropic-key
```

It also runs with no keys at all: memory falls back to a local file, proposals come from a small built-in list of places, and the itinerary comes from simple rules.

Tests: `python -m unittest discover tests -v`

## Files

| File | What it does |
|---|---|
| `app.py` | The Streamlit app: create a trip, then Everyone's input, Packing list, Proposals, Our trip, After the trip, Memory |
| `planner.py` | Proposes destinations, builds the itinerary with a cited reason for every choice, and runs the privacy guard |
| `memory_store.py` | Mem0 scopes (`user_id`, `run_id`, `agent_id`, `app_id`) with an offline fallback, plus the local trips file |
| `llm.py` | Claude / OpenAI wrapper |
| `style.py` | Look and feel: the stylesheet and the HTML cards |

## Built with

Python, [Streamlit](https://streamlit.io), [Mem0](https://mem0.ai) for memory, Claude for proposals and itineraries, and Google Maps for the map.
