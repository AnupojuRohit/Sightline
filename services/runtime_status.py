from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import RLock
from typing import Any

_LOCK = RLock()
_MAX_EVENTS = 200
_EVENTS: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_STATS: dict[str, int] = {
    "context_events": 0,
    "mismatches_found": 0,
    "cards_posted": 0,
    "updates_applied": 0,
    "dismissals": 0,
}
_LAST_EVENT_AT: str | None = None


def record_event(step: str, detail: str, data: dict[str, Any] | None = None) -> None:
    global _LAST_EVENT_AT
    event = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "step": step,
        "detail": detail,
        "data": data or {},
    }
    with _LOCK:
        _EVENTS.appendleft(event)
        _LAST_EVENT_AT = event["ts"]


def increment_stat(name: str, amount: int = 1) -> None:
    with _LOCK:
        _STATS[name] = _STATS.get(name, 0) + amount


def snapshot(max_events: int = 25) -> dict[str, Any]:
    with _LOCK:
        return {
            "lastEventAt": _LAST_EVENT_AT,
            "stats": dict(_STATS),
            "events": list(_EVENTS)[:max_events],
        }
