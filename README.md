# 🏔️ WanderFolk

**A project I built at SF Tech Week 2026**, during the /build-with-AI Buildathon (Mem0 × SVAI Hub × The Gen Academy).

WanderFolk is a simple travel planner agent for a group of friends. Everyone says where they'd love to go, what they eat, how they like to travel and what to pack. WanderFolk proposes 5-6 destinations that fit the whole group, the group picks one, and it shows the Google Map, a day-by-day itinerary and the reason behind every choice.

## How it works

1. **Start a trip:** give it a name, a start city, the number of days, and up to 12 people. No destination needed yet. You get an invite link to share; only people with the link can open the trip.
2. **Who are you?** Each person picks their name once; their phone or laptop remembers it.
3. **Everyone's input:** places you'd love, food and dietary needs, how you like to travel, and your own idea for this trip. Anything can be marked private.
4. **Packing list:** everyone brainstorms what to bring and ticks things off as they're packed.
5. **Proposals:** WanderFolk suggests 5-6 destinations, each with why it fits the group, what to watch out for, rough travel time and budget. Vote, then choose one, or type your own.
6. **Our trip:** an embedded Google Map, directions from your start city, an itinerary, and the note behind each choice.
7. **After the trip:** leave feedback, so the next trip avoids the same mistakes.

It's a web app that works on phones and computers, and can be installed on a phone's home screen (Share → Add to Home Screen on iPhone, or Install app on Android).

## What it remembers

WanderFolk keeps what people tell it in [Mem0](https://mem0.ai), so nobody has to repeat themselves.

| What | Where it lives | Example |
|---|---|---|
| Each person's notes | Mem0 `user_id`, one per person | Priya: "Vegetarian" |
| Feedback on a trip | Mem0 `run_id`, one per trip | Priya: "The 7am hike was way too early" |
| Everything the planner knows | Mem0 `agent_id` + `app_id`, across everyone | "Who has food or dietary needs?" |
| Private notes | Mem0 metadata `private: true` | Maya: "Budget about $100 a day" |
| Trips, votes, packing list, itinerary | Supabase when configured, otherwise a local file in `.data/` | |

Dietary needs, travel style and feedback carry over to each person's next trip. Places and ideas belong to one trip only.

Private notes are used for planning but never shown to the group: the server removes their text before anything reaches someone else's browser, and a privacy guard checks every proposal and itinerary so the wording, the amounts and the owner of a private note don't leak.

## Run it

```bash
pip install -r requirements.txt
cd web && npm install && cd ..
```

Then, in two terminals:

```bash
uvicorn server:app --reload --port 8000     # the API
cd web && npm run dev                       # the trip app, at http://localhost:5173/trip/
```

Or build once (`cd web && npm run build`) and run only `uvicorn server:app --port 8000`, which then serves the start page at http://localhost:8000 and trips at http://localhost:8000/trip/.

To use Mem0 and Claude, create a file named `.env` next to `server.py` with your own keys:

```
MEM0_API_KEY=your-mem0-key
ANTHROPIC_API_KEY=your-anthropic-key
```

It also runs with no keys at all: memory falls back to a local file, proposals come from a small built-in list of places, and the itinerary comes from simple rules.

Optional: set `CREATE_CODE=some-word` to require that word before anyone can start a new trip. Joining a trip by its link never needs it.

Tests: `python -m unittest discover tests -v`

## Hosting it

Trips are saved to a local file by default, which hosting platforms wipe. For a hosted app, keep them in Supabase:

1. Create a free project at [supabase.com](https://supabase.com).
2. In its **SQL Editor**, run [`supabase/schema.sql`](supabase/schema.sql) once.
3. From **Project Settings**, add these to your `.env` (or your host's environment variables):

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

Then deploy on [Vercel](https://vercel.com): import this repo and add the same keys under **Environment Variables**. `vercel.json` builds the web app into `public/` and runs `server.py` as the API.

## Files

| File | What it does |
|---|---|
| `server.py` | The API the web app talks to; filters out other people's private notes |
| `web/public/index.html`, `landing.js` | The start page: plain HTML built with the [taste-skill](https://github.com/Leonxlnx/taste-skill) kit in `web/public/assets`; it starts and joins trips through the API |
| `web/src/`, `web/trip/` | The trip app (React + Vite) at `/trip/`: the trip page and its six tabs, installable on phones |
| `planner.py` | Proposes destinations, builds the itinerary with a cited reason for every choice, and runs the privacy guard |
| `memory_store.py` | Mem0 scopes (`user_id`, `run_id`, `agent_id`, `app_id`) with an offline fallback, plus where trips are saved (local file or Supabase) |
| `llm.py` | Claude / OpenAI wrapper |
| `streamlit_app.py`, `style.py` | The first version, built in Streamlit. Run it with `pip install -r requirements-streamlit.txt` and `streamlit run streamlit_app.py` |

## Built with

Python, FastAPI, React, [Mem0](https://mem0.ai) for memory, Claude for proposals and itineraries, and Google Maps for the map.
