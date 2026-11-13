import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, tripPath, type Config, type TripView } from "./api";
import { AfterTab, InputTab, MemoryTab, PackingTab, ProposalsTab, TripTab } from "./Tabs";
import { Avatar, count, forgetTrip, go, readStore, rememberTrip, useToast, writeStore } from "./ui";

export type Act = (fn: () => Promise<unknown>, done?: string) => Promise<boolean>;

const TABS = [
  { id: "input", icon: "📝", label: "Input", long: "Everyone's input" },
  { id: "pack", icon: "🎒", label: "Packing", long: "Packing list" },
  { id: "props", icon: "💡", label: "Proposals", long: "Proposals" },
  { id: "trip", icon: "🗺️", label: "Our trip", long: "Our trip" },
  { id: "after", icon: "💬", label: "After", long: "After the trip" },
  { id: "memory", icon: "🧠", label: "Memory", long: "Memory" },
] as const;
export type TabId = (typeof TABS)[number]["id"];

export default function TripPage({ tripId, config }: { tripId: string; config: Config | null }) {
  const toast = useToast();
  const meKey = `wf.me.${tripId}`;
  const [me, setMeState] = useState<string | null>(() => readStore<string | null>(meKey, null));
  const [view, setView] = useState<TripView | null>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState<TabId>(() => readStore<TabId>(`wf.tab.${tripId}`, "input"));
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const loading = useRef(false);

  const setMe = (name: string | null) => {
    setMeState(name);
    writeStore(meKey, name);
  };
  const openTab = (t: TabId) => {
    setTab(t);
    writeStore(`wf.tab.${tripId}`, t);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const v = await api<TripView>(tripPath(tripId), { params: { me: me ?? undefined } });
      setView(v);
      rememberTrip(v.trip.id, v.trip.name);
    } catch (err) {
      if (err instanceof ApiError && /doesn't match/.test(err.message)) {
        setMissing(true);
        forgetTrip(tripId);
      }
    } finally {
      loading.current = false;
    }
  }, [tripId, me]);

  // Load now, then keep up with the rest of the group every 15 seconds while the page is visible.
  useEffect(() => {
    refresh();
    const timer = setInterval(() => document.visibilityState === "visible" && refresh(), 15000);
    const onShow = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onShow);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [refresh]);

  // Run a change, say how it went, then reload the trip. Returns true on success.
  const act: Act = async (fn, done) => {
    try {
      await fn();
      if (done) toast(done);
      await refresh();
      return true;
    } catch (err) {
      toast((err as Error).message, true);
      await refresh();
      return false;
    }
  };

  // Long AI runs show a banner instead of freezing the page.
  const slow = async (label: string, fn: () => Promise<unknown>, done: string, then?: TabId) => {
    setBusy(label);
    const ok = await act(fn, done);
    setBusy(null);
    if (ok && then) openTab(then);
  };

  if (missing) {
    return (
      <main className="page">
        <div className="card center">
          <h2>That link doesn't match a trip</h2>
          <p className="muted">It may have been deleted. Check the link with whoever sent it, or start a new trip.</p>
          <button className="btn primary" onClick={() => go(null)}>Go to the start page</button>
        </div>
      </main>
    );
  }
  if (!view) return <main className="page"><div className="loading">Opening the trip…</div></main>;

  const { trip, memories } = view;
  const members = trip.members;
  const meNow = me && members.includes(me) ? me : null;
  const notes = memories.filter((m) => ["place", "diet", "travel", "idea"].includes(m.kind));

  const journey = [
    { t: "Everyone's input", d: "Places, food, travel style", done: notes.length > 0 },
    { t: "Get proposals", d: "Trips that fit the group", done: trip.proposals.length > 0 },
    { t: "Pick a place", d: "Vote, then choose", done: !!trip.chosen },
    { t: "Map and plan", d: "Itinerary and packing", done: !!trip.plan },
  ];
  const now = journey.findIndex((s) => !s.done);
  const waiting = view.waiting_on;
  const next: [string, string | null, TabId | null] =
    now === -1 ? [`You're going to ${trip.chosen!.destination}. The map, itinerary and packing list are ready.`, "Open our trip", "trip"]
    : now === 0 ? ["Say where you'd love to go, what you eat and how you like to travel.", null, null]
    : now === 1 ? [`Input is coming in${waiting.length ? ` (still waiting on ${waiting.join(", ")})` : " from everyone"}. Ask for proposals whenever you're ready.`, "Get proposals", "props"]
    : now === 2 ? ["Proposals are ready. Vote for the ones you'd go on, then choose one together.", "See proposals", "props"]
    : ["Destination chosen. Build the plan to see the map and itinerary.", "Open our trip", "trip"];

  const shared = { view, me: meNow, act, slow, config, openTab };

  return (
    <div className="trip-shell">
      <header className="topbar">
        <button className="icon-btn" onClick={() => go(null)} aria-label="Back to the start page">←</button>
        <div className="topbar-title">
          <span className="brand">WanderFolk</span>
          <span className="topbar-trip">{trip.name}</span>
        </div>
        <button className="icon-btn" onClick={() => setMenu(true)} aria-label="Trip menu">⋯</button>
      </header>

      <main className="page trip-page">
        <section className="hero in">
          <div>
            <div className="hero-kicker">{count(trip.days, "day")}{trip.origin ? ` · from ${trip.origin}` : ""}</div>
            <h1 className="hero-title">{trip.name}</h1>
          </div>
          <div className="stats">
            <div className="stat"><b>{members.length}</b><span>Travelers</span></div>
            <div className="stat"><b>{notes.length}</b><span>Notes</span></div>
            <div className="stat"><b>{trip.packing.length}</b><span>To pack</span></div>
          </div>
        </section>

        <ol className="steps">
          {journey.map((s, i) => (
            <li key={s.t} className={`step ${s.done ? "done" : i === now ? "now" : "todo"}`}>
              <span className="step-n">{s.done ? "✓" : i + 1}</span>
              <span><span className="step-t">{s.t}</span><span className="step-d">{s.d}</span></span>
            </li>
          ))}
        </ol>

        <div className="next">
          <p><b>{now === -1 ? "All set" : "Next step"}:</b> {next[0]}</p>
          {next[1] && next[2] && tab !== next[2] && (
            <button className="btn primary small" onClick={() => openTab(next[2]!)}>{next[1]} →</button>
          )}
        </div>

        <div className="me-bar">
          {meNow ? (
            <>
              <Avatar name={meNow} index={members.indexOf(meNow)} size={28} />
              <span>You're <b>{meNow}</b></span>
              <button className="link" onClick={() => setMe(null)}>Not you?</button>
            </>
          ) : (
            <span className="muted">Just looking. Pick your name below to add things.</span>
          )}
        </div>

        <nav className="tabs" aria-label="Trip sections">
          {TABS.map((t) => (
            <button key={t.id} className={`tab${tab === t.id ? " on" : ""}`} onClick={() => openTab(t.id)} aria-current={tab === t.id}>
              <span aria-hidden>{t.icon}</span>
              <span className="tab-long">{t.long}</span>
              <span className="tab-short">{t.label}</span>
            </button>
          ))}
        </nav>

        {busy && <div className="busy" role="status"><span className="spinner" />{busy}</div>}

        <div className="tab-body">
          {tab === "input" && <InputTab {...shared} />}
          {tab === "pack" && <PackingTab {...shared} />}
          {tab === "props" && <ProposalsTab {...shared} />}
          {tab === "trip" && <TripTab {...shared} />}
          {tab === "after" && <AfterTab {...shared} />}
          {tab === "memory" && <MemoryTab {...shared} />}
        </div>
      </main>

      {!meNow && <WhoAreYou members={members} onPick={setMe} />}
      {menu && <Menu view={view} config={config} act={act} onClose={() => setMenu(false)} />}
    </div>
  );
}

function WhoAreYou({ members, onPick }: { members: string[]; onPick: (n: string) => void }) {
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <div className="sheet-backdrop">
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="who-title">
        <h2 id="who-title">Who are you?</h2>
        <p className="muted">So WanderFolk knows whose input is whose. This device will remember.</p>
        <div className="who-grid">
          {members.map((n, i) => (
            <button key={n} className="who" onClick={() => onPick(n)}>
              <Avatar name={n} index={i} size={44} />
              <span>{n}</span>
            </button>
          ))}
        </div>
        <button className="link" onClick={() => setClosed(true)}>I'm just looking</button>
      </div>
    </div>
  );
}

function Menu({ view, config, act, onClose }: { view: TripView; config: Config | null; act: Act; onClose: () => void }) {
  const toast = useToast();
  const { trip } = view;
  const link = `${location.origin}/trip/?trip=${encodeURIComponent(trip.id)}`;
  const [edit, setEdit] = useState({ origin: trip.origin, days: trip.days, members: trip.members.join("\n") });
  const [sure, setSure] = useState(false);

  async function share() {
    if (navigator.share) {
      try {
        await navigator.share({ title: trip.name, url: link,
          text: `Join our trip "${trip.name}" on WanderFolk${trip.code ? `. Open the link, or enter code ${trip.code} at ${location.host}` : ""}` });
        return;
      } catch {
        /* cancelled: fall through to copy */
      }
    }
    try {
      await navigator.clipboard.writeText(link);
      toast("Invite link copied");
    } catch {
      toast("Couldn't copy. Select the link and copy it yourself.", true);
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(trip.code ?? "");
      toast(`Code ${trip.code} copied`);
    } catch {
      toast("Couldn't copy. Read the code out instead.", true);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (await act(() => api(tripPath(trip.id), { method: "PATCH", body: edit }), "Trip updated")) onClose();
  }

  async function remove() {
    if (await act(() => api(tripPath(trip.id), { method: "DELETE" }), "Trip deleted")) {
      forgetTrip(trip.id);
      go(null);
    }
  }

  const s = config?.status;
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet menu" role="dialog" aria-modal="true" aria-label="Trip menu" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2>{trip.name}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <section>
          <h3>Invite the group</h3>
          {trip.code && (
            <div className="join-code">
              <span className="join-code-label">Trip code</span>
              <span className="join-code-value" aria-label={`Trip code ${trip.code.split("").join(" ")}`}>{trip.code}</span>
              <button className="btn small" onClick={copyCode}>Copy code</button>
            </div>
          )}
          <p className="muted small">Friends can type this code on {location.host} under <b>Join a trip</b>, or open the link. Anyone with either can add their input, so share them only with the group.</p>
          <div className="invite">{link}</div>
          <button className="btn primary" onClick={share}>Share invite link</button>
        </section>

        <details>
          <summary>✏️ Edit this trip</summary>
          <form onSubmit={save} className="stack">
            <label>Starting from<input value={edit.origin} maxLength={80} onChange={(e) => setEdit({ ...edit, origin: e.target.value })} /></label>
            <label>Days
              <select value={edit.days} onChange={(e) => setEdit({ ...edit, days: Number(e.target.value) })}>
                {[1, 2, 3, 4, 5, 6, 7].map((d) => <option key={d}>{d}</option>)}
              </select>
            </label>
            <label>Who's coming?<textarea rows={5} value={edit.members} onChange={(e) => setEdit({ ...edit, members: e.target.value })} /></label>
            <button className="btn">Save</button>
          </form>
        </details>

        {s && (
          <details>
            <summary>⚙️ Under the hood</summary>
            {[["Memory", s.memory], ["AI model", s.ai], ["Trips", s.trips]].map(([label, st]) => (
              <div key={label as string} className="status">
                <span className={`dot${(st as { on: boolean }).on ? " on" : ""}`} />
                <span><b>{label as string}</b> · {(st as { label: string }).label}</span>
              </div>
            ))}
            {s.warning && <p className="notice small">{s.warning}</p>}
          </details>
        )}

        <details>
          <summary>🧹 Delete this trip</summary>
          <p className="muted small">
            Deletes <b>{trip.name}</b> with its ideas, packing list and plan. Dietary needs, travel style and feedback stay
            remembered for each person's next trip. This can't be undone.
          </p>
          <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} /> Yes, delete it</label>
          <button className="btn danger" disabled={!sure} onClick={remove}>Delete trip</button>
        </details>

        <p className="muted small">What WanderFolk keeps and how to delete it: <a href="/privacy.html">Privacy</a></p>
      </div>
    </div>
  );
}
