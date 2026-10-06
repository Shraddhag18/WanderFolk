"""
WanderFolk memory, using Mem0's scopes the way Mem0's shared-memory docs describe:

  user_id  = one traveler          -> personal preferences ("Priya hates early mornings")
  run_id   = one trip              -> shared trip memory  ("7am hike was too early")
  agent_id = the WanderFolk planner   -> everything the planner has learned, across travelers
  app_id   = "roamory"

Mem0Store talks to the Mem0 platform. LocalStore is an offline stand-in with the same methods,
so the demo still works without keys or Wi-Fi.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

AGENT_ID = "roamory-planner"
APP_ID = "roamory"
DATA_DIR = Path(__file__).parent / ".data"
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize(item: dict) -> dict:
    meta = item.get("metadata") or {}
    return {
        "id": item.get("id"),
        "memory": item.get("memory") or "",
        "user_id": item.get("user_id") or meta.get("traveler"),
        "run_id": item.get("run_id") or meta.get("trip_id"),
        "type": meta.get("type", ""),
        "traveler": meta.get("traveler") or item.get("user_id"),
        "trip_id": meta.get("trip_id") or item.get("run_id"),
        "trip_name": meta.get("trip_name", ""),
        "private": bool(meta.get("private", False)),
        "group": meta.get("group", ""),
        "created_at": item.get("created_at", ""),
    }


def _results(resp) -> list:
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        return resp.get("results", resp.get("memories", [])) or []
    return []


class LocalStore:
    name = "Local demo store"
    is_live = False

    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "memories.json"

    def _read(self) -> list:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, items: list) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def add(self, text: str, user_id: str, metadata: dict, run_id: str | None = None) -> dict:
        item = {"id": uuid.uuid4().hex[:12], "memory": text, "user_id": user_id, "run_id": run_id,
                "agent_id": AGENT_ID, "app_id": APP_ID, "metadata": metadata, "created_at": _now()}
        with _lock:
            items = self._read()
            items.append(item)
            self._write(items)
        return _normalize(item)

    def for_traveler(self, user_id: str) -> list[dict]:
        return [_normalize(i) for i in self._read() if i.get("user_id") == user_id]

    def for_travelers(self, user_ids: list[str]) -> list[dict]:
        return [_normalize(i) for i in self._read() if i.get("user_id") in user_ids]

    def shared(self) -> list[dict]:
        """Everything the planner agent knows, across all travelers (agent_id + app_id scope)."""
        return [_normalize(i) for i in self._read() if i.get("agent_id") == AGENT_ID]

    def for_trip(self, run_id: str) -> list[dict]:
        return [_normalize(i) for i in self._read() if i.get("run_id") == run_id]

    def search(self, query: str, limit: int = 6, user_ids: list[str] | None = None) -> list[dict]:
        words = set(re.findall(r"[a-z]{3,}", query.lower()))
        pool = self.for_travelers(user_ids) if user_ids else self.shared()
        scored = [(len(words & set(re.findall(r"[a-z]{3,}", m["memory"].lower()))), m) for m in pool]
        return [m for s, m in sorted(scored, key=lambda x: -x[0]) if s][:limit]

    def delete(self, memory_id: str) -> None:
        with _lock:
            self._write([i for i in self._read() if i.get("id") != memory_id])

    def clear_group(self, travelers: list[str]) -> None:
        with _lock:
            self._write([i for i in self._read() if i.get("user_id") not in travelers])


class Mem0Store:
    """
    infer=False: we store exactly the sentence the traveler gave us (and it's saved immediately,
    which keeps the live demo predictable).
    """
    name = "Mem0 platform"
    is_live = True

    def __init__(self, api_key: str):
        from mem0 import MemoryClient
        self.client = MemoryClient(api_key=api_key)

    def add(self, text: str, user_id: str, metadata: dict, run_id: str | None = None) -> dict:
        kwargs = dict(user_id=user_id, agent_id=AGENT_ID, app_id=APP_ID, metadata=metadata, infer=False)
        if run_id:
            kwargs["run_id"] = run_id
        resp = self.client.add([{"role": "user", "content": text}], **kwargs)
        first = (_results(resp) or [{}])[0]
        return _normalize({"id": first.get("id"), "memory": text, "user_id": user_id,
                           "run_id": run_id, "metadata": metadata, "created_at": _now()})

    def _get_all(self, filters: dict) -> list[dict]:
        resp = self.client.get_all(filters=filters)
        items = [_normalize(i) for i in _results(resp)]
        return sorted(items, key=lambda i: i.get("created_at") or "")

    def for_traveler(self, user_id: str) -> list[dict]:
        try:
            return self._get_all({"user_id": user_id})
        except TypeError:
            return [_normalize(i) for i in _results(self.client.get_all(user_id=user_id))]

    def for_travelers(self, user_ids: list[str]) -> list[dict]:
        """One group's people in one request, so a hosted app never reads other groups' memories."""
        try:
            return self._get_all({"OR": [{"user_id": u} for u in user_ids]})
        except Exception:
            return [m for u in user_ids for m in self.for_traveler(u)]

    def shared(self) -> list[dict]:
        return self._get_all({"AND": [{"agent_id": AGENT_ID}, {"app_id": APP_ID}]})

    def for_trip(self, run_id: str) -> list[dict]:
        return self._get_all({"run_id": run_id})

    def search(self, query: str, limit: int = 6, user_ids: list[str] | None = None) -> list[dict]:
        scope = {"OR": [{"user_id": u} for u in user_ids]} if user_ids else \
            {"AND": [{"agent_id": AGENT_ID}, {"app_id": APP_ID}]}
        resp = self.client.search(query, filters=scope, top_k=limit)
        return [_normalize(i) for i in _results(resp)]

    def delete(self, memory_id: str) -> None:
        self.client.delete(memory_id=memory_id)

    def clear_group(self, travelers: list[str]) -> None:
        for t in travelers:
            self.client.delete_all(user_id=t)


def make_store():
    key = os.getenv("MEM0_API_KEY", "").strip()
    if key and os.getenv("FORCE_LOCAL_MEMORY", "").lower() not in ("1", "true", "yes"):
        try:
            return Mem0Store(key), None
        except Exception as e:
            return LocalStore(), f"Mem0 not available ({e.__class__.__name__}: {e}). Using local demo store."
    return LocalStore(), None


def traveler_id(group: str, name: str) -> str:
    """Mem0 user_id for a traveler, namespaced by group so demos don't collide."""
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "x"
    return f"{slug(group)}--{slug(name)}"


def community_id(destination: str) -> str:
    """Mem0 user_id for a place's community tips, shared by every group that visits it."""
    return "community--" + (re.sub(r"[^a-z0-9]+", "-", destination.lower()).strip("-") or "x")


# ---- trips registry (the itineraries are app data; Mem0 holds what people told us) ----

class TripStore:
    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "trips.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def list(self, group: str) -> list[dict]:
        return self._read().get(group, [])

    def get(self, group: str, trip_id: str) -> dict | None:
        return next((t for t in self.list(group) if t["id"] == trip_id), None)

    def save(self, group: str, trip: dict) -> None:
        with _lock:
            data = self._read()
            trips = [t for t in data.get(group, []) if t["id"] != trip["id"]]
            trips.append(trip)
            data[group] = trips
            DATA_DIR.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def delete(self, group: str, trip_id: str) -> None:
        with _lock:
            data = self._read()
            data[group] = [t for t in data.get(group, []) if t["id"] != trip_id]
            DATA_DIR.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def clear(self, group: str) -> None:
        with _lock:
            data = self._read()
            data.pop(group, None)
            DATA_DIR.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
