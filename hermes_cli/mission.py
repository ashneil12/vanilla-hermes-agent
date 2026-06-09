"""Operator OS mission mode — the object that composes the three loops.

A :class:`Mission` ties a standing goal (``goals.py``, persisted under
``goal:<session_id>``) to a kanban root task, plus the deterministic halt state
(cost ceilings, the mission-level no-progress fingerprint history, turn budget).
The gateway's ``_mission_supervisor_watcher`` ticks each active mission, runs
deterministic hard-halt checks (:func:`decide_tick`), and — Phase 3 — re-judges
against the board. The LLM decides none of the halts.

Persistence mirrors ``goals.py``: SessionDB ``state_meta``, key ``mission:<id>``,
plus an index key ``missions:active`` so a daemon can resume standing missions
after a gateway restart (gap #7 — this registry does NOT exist upstream). The
store is injectable so the registry + decision logic are unit-testable without a
live SessionDB.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from agent.escalation_router import BUDGET_CEILING, NO_PROGRESS

MISSION_META_PREFIX = "mission:"
ACTIVE_INDEX_KEY = "missions:active"
SUPERVISOR_HEARTBEAT_KEY = "mission:supervisor:heartbeat"

STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_PAUSED = "paused"

DEFAULT_NO_PROGRESS_REPEAT = 3
DEFAULT_GLOBAL_AGENT_CEILING = 16
DEFAULT_HEARTBEAT_STALE_SECONDS = 600


@dataclass
class Mission:
    id: str
    goal_session_id: str
    root_task_id: str
    created_at: int = 0
    status: str = STATUS_RUNNING
    max_turns: int = 20
    turns_used: int = 0
    usd_ceiling: Optional[float] = None
    token_ceiling: Optional[int] = None
    board_usd_ceiling: Optional[float] = None
    board_token_ceiling: Optional[int] = None
    global_agent_ceiling: int = DEFAULT_GLOBAL_AGENT_CEILING
    fp_history: List[str] = field(default_factory=list)
    paused_reason: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Mission":
        d = json.loads(raw)
        known = set(cls.__dataclass_fields__)  # tolerate extra/unknown keys
        return cls(**{k: v for k, v in d.items() if k in known})


# --------------------------------------------------------------------------- #
# No-progress detection
# --------------------------------------------------------------------------- #
def board_fingerprint(snapshot: Dict[str, Any]) -> str:
    """Stable 16-hex hash of the board's progress shape. Identical fingerprints
    across consecutive ticks == no forward motion."""
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def is_no_progress(
    fp_history: List[str], *, repeat: int = DEFAULT_NO_PROGRESS_REPEAT
) -> bool:
    """True if the last ``repeat`` fingerprints are identical (stuck)."""
    if len(fp_history) < repeat:
        return False
    tail = fp_history[-repeat:]
    return all(fp == tail[0] for fp in tail)


def format_board_digest(
    counts: Dict[str, int],
    leaf_tasks: Optional[List[Dict[str, Any]]] = None,
    *,
    max_chars: int = 1500,
) -> str:
    """Bounded, judge-readable board digest (gap #2 serializer).

    Lane counts + a completion ratio + a few OUTSTANDING leaf tasks (blocked
    first — the judge cares most about those), capped at ``max_chars`` so a
    50-task board still fits the aux judge's context budget.
    """
    counts = counts or {}
    lane_order = [
        "triage", "todo", "scheduled", "ready", "running",
        "review", "blocked", "done", "archived",
    ]
    lane_line = ", ".join(f"{k}={counts[k]}" for k in lane_order if counts.get(k))
    total = sum(counts.values())
    done = counts.get("done", 0) + counts.get("archived", 0)
    parts = [
        f"lanes: {lane_line or 'empty'}",
        f"completion: {done}/{total} tasks done",
    ]

    def _rank(t: Dict[str, Any]) -> int:
        return 0 if t.get("status") == "blocked" else 1

    for t in sorted(leaf_tasks or [], key=_rank):
        line = f"- [{t.get('status', '?')}] {t.get('id', '?')}: {t.get('title', '')}"
        if len("\n".join(parts)) + len(line) + 1 > max_chars:
            parts.append("- ... (truncated)")
            break
        parts.append(line)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Supervisor tick decision — pure, deterministic. The LLM decides NONE of this.
# --------------------------------------------------------------------------- #
@dataclass
class TickDecision:
    action: str  # "spawn" | "halt"
    halt_reason: Optional[str] = None
    escalate: Optional[str] = None  # an escalation_router reason, or None
    throttle: bool = False  # global agent ceiling hit — skip NEW spawns this tick


def decide_tick(
    mission: Mission,
    *,
    board_usd_spent: float,
    board_tokens_spent: int,
    active_agents: int,
    new_fingerprint: str,
) -> TickDecision:
    """Run the deterministic hard-halt checks for one supervisor tick.

    Order: board budget ceiling -> turn budget -> no-progress. (The board cost
    cap also lives in ``dispatch_once`` as the spawn brake; this is the
    mission-level mirror that pauses the whole mission + escalates.) Mutates
    ``mission.fp_history``; the caller persists the mission afterwards.
    """
    if mission.board_token_ceiling and board_tokens_spent >= mission.board_token_ceiling:
        return TickDecision("halt", "BUDGET_CEILING", BUDGET_CEILING)
    if mission.board_usd_ceiling and board_usd_spent >= mission.board_usd_ceiling:
        return TickDecision("halt", "BUDGET_CEILING", BUDGET_CEILING)
    if mission.turns_used >= mission.max_turns:
        return TickDecision("halt", "TURN_BUDGET_EXHAUSTED", NO_PROGRESS)

    mission.fp_history.append(new_fingerprint)
    if len(mission.fp_history) > 50:
        mission.fp_history = mission.fp_history[-50:]
    if is_no_progress(mission.fp_history):
        return TickDecision("halt", "NO_PROGRESS", NO_PROGRESS)

    if active_agents >= mission.global_agent_ceiling:
        return TickDecision("spawn", None, None, throttle=True)
    return TickDecision("spawn", None, None)


# --------------------------------------------------------------------------- #
# Registry (SessionDB-backed by default; store is injectable for tests)
# --------------------------------------------------------------------------- #
class _SessionDBStore:
    """Default store: SessionDB ``state_meta`` (lazy import, one handle)."""

    def __init__(self) -> None:
        self._db = None

    def _conn(self):
        if self._db is None:
            from hermes_state import SessionDB  # lazy: keeps import light

            self._db = SessionDB()
        return self._db

    def get(self, key: str) -> Optional[str]:
        return self._conn().get_meta(key)

    def set(self, key: str, value: str) -> None:
        self._conn().set_meta(key, value)


def _default_store():
    return _SessionDBStore()


def save_mission(m: Mission, *, store=None) -> None:
    store = store or _default_store()
    store.set(MISSION_META_PREFIX + m.id, m.to_json())
    if m.status == STATUS_RUNNING:
        _index_add(store, m.id)
    else:
        _index_remove(store, m.id)


def load_mission(mission_id: str, *, store=None) -> Optional[Mission]:
    store = store or _default_store()
    raw = store.get(MISSION_META_PREFIX + mission_id)
    return Mission.from_json(raw) if raw else None


def list_active_mission_ids(*, store=None) -> List[str]:
    store = store or _default_store()
    raw = store.get(ACTIVE_INDEX_KEY)
    return json.loads(raw) if raw else []


def _index_add(store, mid: str) -> None:
    ids = list_active_mission_ids(store=store)
    if mid not in ids:
        ids.append(mid)
        store.set(ACTIVE_INDEX_KEY, json.dumps(ids))


def _index_remove(store, mid: str) -> None:
    ids = [i for i in list_active_mission_ids(store=store) if i != mid]
    store.set(ACTIVE_INDEX_KEY, json.dumps(ids))


def pause_mission(m: Mission, reason: str, *, store=None) -> None:
    m.status = STATUS_PAUSED
    m.paused_reason = reason
    save_mission(m, store=store)


def mark_done(m: Mission, *, store=None) -> None:
    m.status = STATUS_DONE
    save_mission(m, store=store)


# --------------------------------------------------------------------------- #
# Supervisor heartbeat (for the watchdog-over-the-watcher)
# --------------------------------------------------------------------------- #
def write_supervisor_heartbeat(*, store=None, now: Optional[float] = None) -> None:
    store = store or _default_store()
    ts = int(time.time() if now is None else now)
    store.set(SUPERVISOR_HEARTBEAT_KEY, str(ts))


def supervisor_heartbeat_stale(
    *, store=None, now: Optional[float] = None,
    threshold_seconds: int = DEFAULT_HEARTBEAT_STALE_SECONDS,
) -> bool:
    """True if the supervisor's last heartbeat is older than the threshold.

    Returns False when no heartbeat exists yet (never started -> nothing to
    alarm on). The watchdog (a cheap separate tick) calls this and escalates
    DISPATCHER_STUCK-style if the supervisor wedged.
    """
    store = store or _default_store()
    raw = store.get(SUPERVISOR_HEARTBEAT_KEY)
    if not raw:
        return False
    ts = int(time.time() if now is None else now)
    try:
        last = int(raw)
    except (TypeError, ValueError):
        return False
    return (ts - last) >= threshold_seconds


__all__ = [
    "Mission",
    "TickDecision",
    "board_fingerprint",
    "format_board_digest",
    "is_no_progress",
    "decide_tick",
    "save_mission",
    "load_mission",
    "list_active_mission_ids",
    "pause_mission",
    "mark_done",
    "write_supervisor_heartbeat",
    "supervisor_heartbeat_stale",
    "STATUS_RUNNING",
    "STATUS_DONE",
    "STATUS_PAUSED",
    "SUPERVISOR_HEARTBEAT_KEY",
]
