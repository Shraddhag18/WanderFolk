// Shapes the API returns (see server.py) and one small fetch helper.

export type Category = { kind: string; icon: string; question: string; example: string };
export type Status = { label: string; on: boolean };
export type Config = {
  create_code_required: boolean;
  max_members: number;
  categories: Category[];
  status: { memory: Status; ai: Status; trips: Status; warning: string | null };
  app_id: string;
};

export type Memory = {
  id: string;
  traveler: string;
  kind: string;
  private: boolean;
  text: string | null; // null: someone else's private note
  mine: boolean;
  from_trip: string | null;
  can_delete: boolean;
  can_edit: boolean;
};

export type Proposal = {
  id: string;
  destination: string;
  tagline: string;
  why: string[];
  watch_out: string;
  travel: string;
  budget: string;
  highlights: string[];
};

export type Change = { action: string; because: string; who: string; private: boolean; kind: string; trip: string };
export type Day = { day: number | string; items: { time: string; activity: string }[] };
export type Plan = { days: Day[]; changes?: Change[]; packing?: string[]; redactions?: number; engine?: string };
export type PackItem = { id: string; text: string; by: string; done: boolean };

export type Trip = {
  id: string;
  code?: string; // short join code, like K7P-4QM
  name: string;
  origin: string;
  days: number;
  members: string[];
  created_at: string;
  packing: PackItem[];
  proposals: Proposal[];
  votes: Record<string, string[]>;
  chosen: Proposal | null;
  plan: Plan | null;
  proposals_engine?: string;
  memories_used?: number;
};

export type TripView = {
  trip: Trip;
  memories: Memory[];
  waiting_on: string[];
  limits: { suggest_left: number; plan_left: number };
};

export class ApiError extends Error {}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown; params?: Record<string, string | undefined> } = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.params ?? {})) if (v) qs.set(k, v);
  const url = `/api${path}${qs.size ? `?${qs}` : ""}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? "GET",
      headers: opts.body ? { "Content-Type": "application/json" } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach WanderFolk. Check your connection and try again.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    throw new ApiError(typeof detail === "string" ? detail : "Something went wrong. Try again.");
  }
  return data as T;
}

export const tripPath = (id: string) => `/trips/${encodeURIComponent(id)}`;
