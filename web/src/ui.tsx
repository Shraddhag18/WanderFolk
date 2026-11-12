// Small shared pieces: toasts, local storage, avatars, and display helpers.
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

// ---- navigation: the open trip lives in the address bar as ?trip=<id> ----
export function go(tripId: string | null) {
  const url = tripId ? `/?trip=${encodeURIComponent(tripId)}` : "/";
  history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}

// ---- toasts ----
type Toast = { id: number; text: string; bad?: boolean };
const ToastCtx = createContext<(text: string, bad?: boolean) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastHost({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const show = useCallback((text: string, bad = false) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, bad }].slice(-2)); // the latest two; older ones are already stale
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), bad ? 5000 : 2800);
  }, []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast${t.bad ? " bad" : ""}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

// ---- browser storage: only conveniences (who you are on this device, trips you opened) ----
export function readStore<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function writeStore(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode: fine, it just won't be remembered */
  }
}

export type RecentTrip = { id: string; name: string; at: number };
export function rememberTrip(id: string, name: string) {
  const list = readStore<RecentTrip[]>("wf.recent", []).filter((t) => t.id !== id);
  writeStore("wf.recent", [{ id, name, at: Date.now() }, ...list].slice(0, 8));
}
export function forgetTrip(id: string) {
  writeStore("wf.recent", readStore<RecentTrip[]>("wf.recent", []).filter((t) => t.id !== id));
}

// ---- display helpers ----
export const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

const AVATAR = ["#e4572e", "#0f766e", "#7c3aed", "#d97706", "#2563eb", "#be185d"];
export function Avatar({ name, index, size = 36 }: { name: string; index: number; size?: number }) {
  return (
    <span className="avatar" style={{ background: AVATAR[index % AVATAR.length], width: size, height: size, fontSize: size * 0.42 }} aria-hidden>
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

export const KIND_ICON: Record<string, string> = { place: "📍", diet: "🥗", travel: "🚗", idea: "💡", feedback: "💬" };

const ACTIVITY_ICONS: [RegExp, string][] = [
  [/arrive|check in/i, "🏨"], [/\bdrive to\b|driving/i, "🚗"], [/tour|museum/i, "🗺️"], [/hik|trail|walk/i, "🥾"],
  [/beach|tide|ocean|surf/i, "🏖️"], [/overlook|view|falls|bridge|sunset/i, "🌅"], [/breakfast|coffee|caf[eé]/i, "☕"],
  [/lunch|taco|food/i, "🌮"], [/dinner|picnic|restaurant/i, "🍽️"], [/shop/i, "🛍️"], [/nap|downtime|relax|rest/i, "😌"],
];
export const activityIcon = (a: string) => ACTIVITY_ICONS.find(([re]) => re.test(a))?.[1] ?? "📍";

export const mapsSearch = (place: string) => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place)}`;
export const mapsDirections = (from: string, to: string) =>
  `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(from)}&destination=${encodeURIComponent(to)}`;
export const mapsEmbed = (place: string) => `https://www.google.com/maps?q=${encodeURIComponent(place)}&output=embed`;

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Hood({ children }: { children: ReactNode }) {
  return <p className="hood">Under the hood: {children}</p>;
}
