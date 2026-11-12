import { useState, type FormEvent } from "react";
import { api, type Config } from "./api";
import { go, readStore, useToast, type RecentTrip } from "./ui";

export default function Home({ config }: { config: Config | null }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", origin: "", days: 3, members: "", earlier: "", code: "" });
  const [link, setLink] = useState("");
  const [showEarlier, setShowEarlier] = useState(false);
  const recent = readStore<RecentTrip[]>("wf.recent", []);
  const bad = new URLSearchParams(location.search).has("trip");
  const max = config?.max_members ?? 12;

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: k === "days" ? Number(e.target.value) : e.target.value }));

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const { id } = await api<{ id: string }>("/trips", { method: "POST", body: form });
      toast(`${form.name.trim()} created. Invite the others with the link.`);
      go(id);
    } catch (err) {
      toast((err as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function join(e: FormEvent) {
    e.preventDefault();
    if (!link.trim()) return;
    try {
      const { id } = await api<{ id: string }>("/lookup", { params: { link } });
      go(id);
    } catch (err) {
      toast((err as Error).message, true);
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <div>
          <div className="hero-kicker">Group trip planner</div>
          <h1 className="hero-title">WanderFolk</h1>
          <p className="hero-sub">Plan trips with friends. WanderFolk remembers what everyone likes, and what went wrong last time.</p>
        </div>
      </header>

      {bad && <div className="notice">That link doesn't match a trip. Check it with whoever sent it, or start a new trip.</div>}

      <div className="home-grid">
        <section className="card">
          <h2>Start a group trip</h2>
          <p className="muted">Name the trip and add who's coming. No destination needed yet: WanderFolk proposes some once everyone has had their say.</p>
          <form onSubmit={create} className="stack">
            <label>
              Trip name
              <input required maxLength={80} value={form.name} onChange={set("name")} placeholder="e.g. Summer getaway 2026" />
            </label>
            <div className="row-2">
              <label>
                Starting from
                <input maxLength={80} value={form.origin} onChange={set("origin")} placeholder="e.g. San Francisco" />
              </label>
              <label className="days">
                Days
                <select value={form.days} onChange={set("days")}>
                  {[1, 2, 3, 4, 5, 6, 7].map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
            </div>
            <label>
              Who's coming? <span className="faint">(up to {max})</span>
              <textarea required rows={4} value={form.members} onChange={set("members")} placeholder="One name per line, or separated by commas" />
            </label>
            {showEarlier ? (
              <label>
                Earlier trip link
                <input value={form.earlier} onChange={set("earlier")} placeholder="Paste it to carry over dietary needs and feedback" />
              </label>
            ) : (
              <button type="button" className="link" onClick={() => setShowEarlier(true)}>Travelled together before? Carry over what WanderFolk learned →</button>
            )}
            {config?.create_code_required && (
              <label>
                Access code
                <input type="password" value={form.code} onChange={set("code")} autoComplete="off" />
              </label>
            )}
            <button className="btn primary" disabled={busy}>{busy ? "Creating…" : "Create trip"}</button>
          </form>
        </section>

        <div className="stack">
          <section className="card">
            <h2>Join a trip</h2>
            <p className="muted">Got a link from a friend? Open it, or paste it here.</p>
            <form onSubmit={join} className="inline-form">
              <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="Trip link or code" aria-label="Trip link or code" />
              <button className="btn">Open</button>
            </form>
          </section>

          {recent.length > 0 && (
            <section className="card">
              <h2>On this device</h2>
              <div className="recent">
                {recent.map((t) => (
                  <button key={t.id} className="recent-item" onClick={() => go(t.id)}>
                    <span>🗺️ {t.name}</span>
                    <span className="faint">→</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="card how">
            <h2>How it works</h2>
            <ol>
              <li><b>Everyone adds input:</b> places, food needs, travel style, ideas. Anything can be private.</li>
              <li><b>WanderFolk proposes</b> 5–6 destinations that fit the whole group.</li>
              <li><b>Vote and choose</b>, then get a map and a day-by-day plan with the reason behind every choice.</li>
              <li><b>Leave feedback</b> so the next trip avoids the same mistakes.</li>
            </ol>
          </section>
        </div>
      </div>
    </main>
  );
}
