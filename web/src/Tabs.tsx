import { useState, type FormEvent } from "react";
import { api, tripPath, type Change, type Config, type Memory, type TripView } from "./api";
import type { Act, TabId } from "./Trip";
import { activityIcon, Avatar, count, Empty, Hood, KIND_ICON, mapsDirections, mapsEmbed, mapsSearch, useToast } from "./ui";

type Shared = {
  view: TripView;
  me: string | null;
  act: Act;
  slow: (label: string, fn: () => Promise<unknown>, done: string, then?: TabId) => Promise<void>;
  config: Config | null;
  openTab: (t: TabId) => void;
};

const noteText = (m: Memory) => (m.text === null ? "🔒 Private note" : `${m.private ? "🔒 " : ""}${m.text}`);

function NeedMe({ me, children }: { me: string | null; children: string }) {
  if (me) return null;
  return <div className="notice">Pick your name first (tap <b>Not you?</b> or reload the page) to {children}.</div>;
}

function NoteRow({ m, onDelete }: { m: Memory; onDelete?: () => void }) {
  return (
    <li className={`note${m.private ? " lock" : ""}`}>
      <span className="note-icon" aria-hidden>{KIND_ICON[m.kind] ?? "💜"}</span>
      <span className="note-text">
        {noteText(m)}
        {m.from_trip && <span className="faint"> · remembered from {m.from_trip}</span>}
      </span>
      {onDelete && m.can_delete && <button className="icon-btn small" onClick={onDelete} aria-label="Delete this note">🗑️</button>}
    </li>
  );
}

// ---------------------------------------------------------------------------
// 1. Everyone's input
// ---------------------------------------------------------------------------

export function InputTab({ view, me, act, config }: Shared) {
  const { trip, memories } = view;
  const cats = config?.categories ?? [];
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [priv, setPriv] = useState(false);
  const [saving, setSaving] = useState(false);
  const mine = memories.filter((m) => m.traveler === me);
  const del = (id: string) => act(() => api(`${tripPath(trip.id)}/memories/${id}`, { method: "DELETE", params: { me: me ?? "" } }), "Deleted");

  async function save(e: FormEvent) {
    e.preventDefault();
    const filled = Object.values(answers).filter((v) => v.trim()).length;
    setSaving(true);
    const ok = await act(() => api(`${tripPath(trip.id)}/notes`, { method: "POST", body: { me, answers, private: priv } }),
      `Saved ${count(filled, "note")} for ${me}`);
    setSaving(false);
    if (ok) {
      setAnswers({});
      setPriv(false);
    }
  }

  return (
    <div className="stack-lg">
      <NeedMe me={me}>add your input</NeedMe>
      {me && (
        <section className="card">
          <h2>{me}, what would make this trip great?</h2>
          <p className="muted">Fill in as many or as few as you like. Food needs and travel style are remembered for your next trips too.</p>
          <form onSubmit={save} className="stack">
            <div className="grid-2">
              {cats.map((c) => (
                <label key={c.kind}>
                  {c.icon} {c.question}
                  <input value={answers[c.kind] ?? ""} maxLength={500} placeholder={c.example}
                    onChange={(e) => setAnswers({ ...answers, [c.kind]: e.target.value })} />
                </label>
              ))}
            </div>
            <label className="check">
              <input type="checkbox" checked={priv} onChange={(e) => setPriv(e.target.checked)} />
              <span>🔒 Keep what I'm adding now private <span className="faint">· WanderFolk still plans around it, but the group never sees the note or who wrote it.</span></span>
            </label>
            <button className="btn primary" disabled={saving}>{saving ? "Saving…" : `Save for ${me}`}</button>
          </form>
          {mine.length > 0 && (
            <details className="mine">
              <summary>What WanderFolk knows about you · {mine.length}</summary>
              <ul className="notes">{mine.map((m) => <NoteRow key={m.id} m={m} onDelete={() => del(m.id)} />)}</ul>
            </details>
          )}
        </section>
      )}

      <section>
        <h2 className="section-title">Everyone so far</h2>
        <div className="members">
          {trip.members.map((p, i) => {
            const theirs = memories.filter((m) => m.traveler === p);
            return (
              <div key={p} className={`member${p === me ? " me" : ""}`}>
                <div className="person"><Avatar name={p} index={i} /><span className="person-name">{p}{p === me ? " (you)" : ""}</span></div>
                {theirs.length ? (
                  <div className="chips">{theirs.map((m) => <span key={m.id} className={`chip${m.private ? " lock" : ""}`}>{KIND_ICON[m.kind]} {noteText(m)}</span>)}</div>
                ) : <p className="faint small">Hasn't added anything yet</p>}
              </div>
            );
          })}
        </div>
        <Hood>each person has their own memory in Mem0, scoped by <code>user_id</code>.</Hood>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Packing list
// ---------------------------------------------------------------------------

export function PackingTab({ view, me, act }: Shared) {
  const { trip } = view;
  const [text, setText] = useState("");
  const [ticks, setTicks] = useState<Record<string, boolean>>({}); // shown right away, before the server answers
  const have = new Set(trip.packing.map((i) => i.text.toLowerCase()));
  const suggested = (trip.plan?.packing ?? []).filter((s) => !have.has(s.toLowerCase()));
  const items = trip.packing.map((i) => ({ ...i, done: ticks[i.id] ?? i.done }));
  const packed = items.filter((i) => i.done).length;

  async function add(e: FormEvent) {
    e.preventDefault();
    if (await act(() => api(`${tripPath(trip.id)}/packing`, { method: "POST", body: { me, text } }), "Added")) setText("");
  }
  async function tick(id: string, done: boolean) {
    setTicks((t) => ({ ...t, [id]: done }));
    await act(() => api(`${tripPath(trip.id)}/packing/${id}`, { method: "PATCH", body: { done } }));
    setTicks((t) => { const { [id]: _, ...rest } = t; return rest; });
  }

  return (
    <div className="stack-lg">
      <section className="card">
        <h2>What do we need to bring?</h2>
        <p className="muted">Everyone adds whatever comes to mind. Tick things off as they get packed.</p>
        <NeedMe me={me}>add to the list</NeedMe>
        {me && (
          <form onSubmit={add} className="inline-form">
            <input value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
              placeholder="e.g. Sunscreen, first-aid kit, speaker" aria-label={`${me} suggests`} />
            <button className="btn primary">Add</button>
          </form>
        )}
        {suggested.length > 0 && (
          <div className="suggest">
            <b>WanderFolk suggests for this trip</b>
            <div className="chips">{suggested.map((s) => <span key={s} className="chip tip">{s}</span>)}</div>
            <button className="btn small" onClick={() => act(() => api(`${tripPath(trip.id)}/packing/suggested`, { method: "POST" }), "Added WanderFolk's suggestions")}>
              Add these to the list
            </button>
          </div>
        )}
      </section>

      {items.length ? (
        <section className="card">
          <div className="progress-head"><b>{packed} of {items.length} packed</b></div>
          <div className="progress" aria-hidden><span style={{ width: `${(100 * packed) / items.length}%` }} /></div>
          <ul className="pack-list">
            {items.map((i) => (
              <li key={i.id} className={i.done ? "done" : ""}>
                <label className="check">
                  <input type="checkbox" checked={i.done} onChange={(e) => tick(i.id, e.target.checked)} />
                  <span>{i.text} <span className="faint">· {i.by}</span></span>
                </label>
                <button className="icon-btn small" aria-label={`Remove ${i.text}`}
                  onClick={() => act(() => api(`${tripPath(trip.id)}/packing/${i.id}`, { method: "DELETE" }))}>🗑️</button>
              </li>
            ))}
          </ul>
        </section>
      ) : <Empty>Nothing on the list yet. Add the first thing above.</Empty>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Proposals
// ---------------------------------------------------------------------------

export function ProposalsTab({ view, me, act, slow }: Shared) {
  const { trip, waiting_on, limits } = view;
  const [own, setOwn] = useState("");
  const toast = useToast();
  const votes = trip.votes ?? {};
  const most = Math.max(0, ...Object.values(votes).map((v) => v.length));

  const suggest = () => slow("Reading everyone's input and looking for places that fit…",
    () => api(`${tripPath(trip.id)}/proposals`, { method: "POST" }), "Proposals ready");
  const choose = (body: object, place: string) => slow(`Planning ${place} around everyone's input…`,
    () => api(`${tripPath(trip.id)}/choose`, { method: "POST", body }), `${place} it is!`, "trip");

  return (
    <div className="stack-lg">
      <section className="card">
        <h2>Where could we go?</h2>
        <p className="muted">WanderFolk reads everyone's input and suggests trips that fit the whole group.</p>
        <p className="small">{waiting_on.length ? <>⏳ No input yet from <b>{waiting_on.join(", ")}</b></> : "✅ Everyone has added their input."}</p>
        <button className="btn primary" onClick={suggest} disabled={limits.suggest_left <= 0}>
          ✨ {trip.proposals.length ? "Suggest again with the latest input" : "Suggest trips for us"}
        </button>
        {limits.suggest_left <= 0 && <p className="faint small">This trip has used all its rounds of proposals.</p>}
      </section>

      {trip.proposals_engine === "rules" && trip.proposals.length > 0 && (
        <div className="notice">No AI model is connected, so these come from a small built-in list of places.</div>
      )}

      {trip.proposals.length ? (
        <div className="props">
          {trip.proposals.map((p, i) => {
            const voters = (votes[p.id] ?? []).filter((v) => trip.members.includes(v));
            const voted = !!me && voters.includes(me);
            const lead = voters.length > 0 && voters.length === most;
            return (
              <article key={p.id} className={`card prop${trip.chosen?.id === p.id ? " chosen" : ""}`}>
                <h3 className="prop-title">{i + 1}. {p.destination}{lead && " 🏆"}</h3>
                {p.tagline && <p className="prop-tag">{p.tagline}</p>}
                <div className="chips">
                  {p.travel && <span className="chip">🚗 {p.travel}</span>}
                  {p.budget && <span className="chip">💰 {p.budget}</span>}
                  {p.highlights.map((h) => <span key={h} className="chip">✨ {h}</span>)}
                </div>
                {p.why.length > 0 && <ul className="prop-why">{p.why.map((w) => <li key={w}>{w}</li>)}</ul>}
                {p.watch_out && <div className="prop-watch">⚠️ {p.watch_out}</div>}
                <p className="prop-votes">{voters.length ? <><b>👍 {voters.length}</b> · {voters.join(", ")}</> : "No votes yet"}</p>
                <div className="actions">
                  <button className={`btn small${voted ? " on" : ""}`} aria-pressed={voted}
                    onClick={() => me ? act(() => api(`${tripPath(trip.id)}/votes`, { method: "POST", body: { me, proposal_id: p.id } })) : toast("Pick your name first to vote.", true)}>
                    {voted ? "👍 You'd go · undo" : "👍 I'd go"}
                  </button>
                  <a className="btn small" href={mapsSearch(p.destination)} target="_blank" rel="noreferrer">🗺️ Map</a>
                  <button className="btn small primary" onClick={() => choose({ proposal_id: p.id }, p.destination)} disabled={limits.plan_left <= 0}>✅ Choose</button>
                </div>
              </article>
            );
          })}
        </div>
      ) : <Empty>Proposals will appear here: 5–6 places, why each fits your group, and what to watch out for.</Empty>}

      <section className="card">
        <form onSubmit={(e) => { e.preventDefault(); if (own.trim()) choose({ destination: own }, own.trim()); }} className="stack">
          <label>Already know where you're going?
            <div className="inline-form">
              <input value={own} onChange={(e) => setOwn(e.target.value)} maxLength={100} placeholder="e.g. Lake Tahoe" />
              <button className="btn" disabled={!own.trim() || limits.plan_left <= 0}>Choose it</button>
            </div>
          </label>
        </form>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Our trip
// ---------------------------------------------------------------------------

function WhyCard({ c, me }: { c: Change; me: string | null }) {
  const kind = c.private ? "private" : c.kind;
  const mine = !c.private && !!me && c.who === me;
  const who = mine ? "you" : c.who || "someone";
  const [icon, cls] = ({ feedback: ["🗣️", "fb"], community: ["🌍", "co"], private: ["🔒", "pr"] } as Record<string, string[]>)[kind] ?? ["💜", ""];
  const reason =
    kind === "private" ? <>Because of a private preference. The planner knows whose, the group doesn't.</>
    : kind === "community" ? <>Because another traveler reported: <i>“{c.because}”</i></>
    : kind === "feedback" ? <>Because {who} said after {c.trip || "the last trip"}: <i>“{c.because}”</i></>
    : <>Because {who} said: <i>“{c.because}”</i></>;
  return (
    <div className={`why ${cls}${mine ? " mine" : ""}`}>
      <div className="why-action">{icon} {c.action}{mine && <span className="you">From you</span>}</div>
      <div className="why-because">{reason}</div>
    </div>
  );
}

export function TripTab({ view, me, slow, openTab }: Shared) {
  const { trip, limits } = view;
  if (!trip.chosen) {
    return (
      <div className="stack-lg">
        <Empty>Choose a destination in Proposals and the map and itinerary will appear here.</Empty>
        <button className="btn primary center-btn" onClick={() => openTab("props")}>Go to proposals →</button>
      </div>
    );
  }
  const place = trip.chosen.destination;
  const plan = trip.plan;
  return (
    <div className="stack-lg">
      <section className="card">
        <h2>📍 {place}</h2>
        {trip.chosen.tagline && <p className="muted">{trip.chosen.tagline}</p>}
        <iframe className="map" title={`Map of ${place}`} src={mapsEmbed(place)} loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
        <div className="actions">
          <a className="btn small" href={mapsSearch(place)} target="_blank" rel="noreferrer">🗺️ Open in Google Maps</a>
          {trip.origin && <a className="btn small" href={mapsDirections(trip.origin, place)} target="_blank" rel="noreferrer">🚗 Directions from {trip.origin}</a>}
          <button className="btn small" disabled={limits.plan_left <= 0}
            onClick={() => slow("Planning with the latest input…", () => api(`${tripPath(trip.id)}/plan`, { method: "POST" }), "Plan updated")}>
            🔄 Re-plan with the latest input
          </button>
        </div>
      </section>

      {plan && (
        <div className="plan">
          <section>
            <h2 className="section-title">The itinerary</h2>
            {plan.days.map((d) => (
              <div key={String(d.day)} className="day">
                <div className="day-title">Day {d.day}</div>
                {d.items.map((it, j) => (
                  <div key={j} className="stop">
                    <span className="stop-time">{it.time}</span>
                    <span className="stop-dot" />
                    <span className="stop-what">{activityIcon(it.activity)} {it.activity}</span>
                  </div>
                ))}
              </div>
            ))}
          </section>
          <section>
            <h2 className="section-title">🧠 Why the plan looks like this</h2>
            {plan.changes?.length ? plan.changes.map((c, i) => <WhyCard key={i} c={c} me={me} />) : <Empty>No notes shaped this plan yet.</Empty>}
            {!!plan.redactions && <p className="faint small">🛡️ Privacy guard removed {count(plan.redactions, "leak")} of private notes.</p>}
            <Hood>used {trip.memories_used ?? 0} memories · planner: {plan.engine === "ai" ? "AI" : "offline rules"}</Hood>
          </section>
        </div>
      )}
      <p className="faint small">Changed your minds? Choose a different place in Proposals.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5. After the trip
// ---------------------------------------------------------------------------

export function AfterTab({ view, me, act }: Shared) {
  const { trip, memories } = view;
  const [text, setText] = useState("");
  const said = memories.filter((m) => m.kind === "feedback" && !m.from_trip);
  async function send(e: FormEvent) {
    e.preventDefault();
    if (await act(() => api(`${tripPath(trip.id)}/feedback`, { method: "POST", body: { me, text } }), `Feedback saved for ${me}`)) setText("");
  }
  return (
    <div className="stack-lg">
      <section className="card">
        <h2>How did it go{me ? `, ${me}` : ""}?</h2>
        <p className="muted">What worked? What didn't? WanderFolk remembers this for your next trip, so the same mistake doesn't happen twice.</p>
        <NeedMe me={me}>leave feedback</NeedMe>
        {me && (
          <form onSubmit={send} className="stack">
            <textarea rows={3} value={text} maxLength={1000} onChange={(e) => setText(e.target.value)}
              placeholder="e.g. The 7am start was too early" aria-label={`${me}'s feedback`} />
            <button className="btn primary" disabled={!text.trim()}>Add feedback</button>
          </form>
        )}
      </section>
      {said.length > 0 && (
        <section className="card">
          <h3>What the group said about this trip</h3>
          <ul className="notes">{said.map((m) => <li key={m.id} className="note"><b>{m.traveler}:</b>&nbsp;{noteText(m)}</li>)}</ul>
        </section>
      )}
      <Hood>feedback goes to this trip's shared memory in Mem0, <code>run_id={trip.id}</code>.</Hood>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 6. Memory
// ---------------------------------------------------------------------------

export function MemoryTab({ view, me, act, config }: Shared) {
  const { trip, memories } = view;
  const [q, setQ] = useState("Who has food or dietary needs?");
  const [hits, setHits] = useState<Memory[] | null>(null);
  const [searching, setSearching] = useState(false);
  const toast = useToast();

  async function search(e: FormEvent) {
    e.preventDefault();
    setSearching(true);
    try {
      setHits((await api<{ hits: Memory[] }>(`${tripPath(trip.id)}/search`, { params: { q, me: me ?? undefined } })).hits);
    } catch (err) {
      toast((err as Error).message, true);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="stack-lg">
      <section className="card">
        <h2>What WanderFolk remembers</h2>
        <p className="muted">{me ? <>Viewing as <b>{me}</b>. </> : null}Private notes stay hidden from everyone except their owner.</p>
        <form onSubmit={search} className="inline-form">
          <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} aria-label="Ask about the group" />
          <button className="btn" disabled={searching}>{searching ? "…" : "Search"}</button>
        </form>
        {hits && (hits.length
          ? <ul className="notes">{hits.map((m) => <li key={m.id} className="note"><b>{m.traveler}:</b>&nbsp;{noteText(m)}</li>)}</ul>
          : <p className="faint small">No matches.</p>)}
        <Hood>one search across every traveler · Mem0 <code>app_id={config?.app_id ?? "roamory"}</code></Hood>
      </section>

      {trip.members.map((p, i) => {
        const theirs = memories.filter((m) => m.traveler === p);
        return (
          <details key={p} className="card person-mem">
            <summary><Avatar name={p} index={i} size={28} /> <b>{p}</b> <span className="faint">· {theirs.length} saved</span></summary>
            {theirs.length ? (
              <ul className="notes">
                {theirs.map((m) => <NoteRow key={m.id} m={m}
                  onDelete={() => act(() => api(`${tripPath(trip.id)}/memories/${m.id}`, { method: "DELETE", params: { me: me ?? "" } }), "Memory deleted")} />)}
              </ul>
            ) : <p className="faint small">Nothing saved yet.</p>}
          </details>
        );
      })}
    </div>
  );
}
