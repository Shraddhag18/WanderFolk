-- WanderFolk: where trips live when the app is hosted.
-- Run this once in Supabase: SQL Editor -> New query -> paste -> Run.

create table if not exists public.trips (
  id         text primary key,
  bucket     text not null default 'trips',
  data       jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists trips_bucket_idx on public.trips (bucket, created_at);

-- Lock the table: with row level security on and no policies, the public "anon" key can't read or write it.
-- The app uses the secret service_role key, which is allowed through.
alter table public.trips enable row level security;

-- Only the app's service_role key may use this table through the Data API; the public keys get nothing.
-- (Needed when "Automatically expose new tables" is off in the project's Data API settings.)
grant select, insert, update, delete on public.trips to service_role;
revoke all on public.trips from anon, authenticated;
