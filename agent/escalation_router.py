"""Escalation router for Operator OS mission mode.

In autonomous ("permissionless") operation the agent runs without per-action
approval, but a NARROW set of conditions must still reach a human:

- ``NEW_SECRET_REQUIRED`` — a credential/API key it cannot obtain itself
- ``PURCHASE`` — anything that spends real money
- ``IRREVERSIBLE`` — prod deploy, mass delete, force-push, DB drop, etc.
- ``PLAN_APPROVAL`` — the one optional up-front plan gate
- ``BUDGET_CEILING`` — the mission's token/$ cap tripped
- ``NO_PROGRESS`` — the mission-level no-progress detector tripped
- ``DISPATCHER_STUCK`` — the kanban dispatcher wedged
- ``N_DENIALS`` — too many consecutive smart-approval denials

Everything else is auto-allowed, subject to the sandbox and the
non-bypassable hardline floor in ``tools/approval.py``. This module decides
WHEN to interrupt the human and sends a *deduplicated* notification via the
existing transports (ntfy / send_message), degrading safely to a logged record
when no transport is configured — a notifier failure must never crash the loop.

The transport is injectable so the policy (which reasons, dedup) is unit
testable without a live notifier. ``PushNotification`` does NOT exist in Hermes;
do not reach for it.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

NEW_SECRET_REQUIRED = "NEW_SECRET_REQUIRED"
PURCHASE = "PURCHASE"
IRREVERSIBLE = "IRREVERSIBLE"
PLAN_APPROVAL = "PLAN_APPROVAL"
BUDGET_CEILING = "BUDGET_CEILING"
NO_PROGRESS = "NO_PROGRESS"
DISPATCHER_STUCK = "DISPATCHER_STUCK"
N_DENIALS = "N_DENIALS"

ESCALATION_REASONS = frozenset(
    {
        NEW_SECRET_REQUIRED,
        PURCHASE,
        IRREVERSIBLE,
        PLAN_APPROVAL,
        BUDGET_CEILING,
        NO_PROGRESS,
        DISPATCHER_STUCK,
        N_DENIALS,
    }
)

DEFAULT_DEDUP_WINDOW_SECONDS = 24 * 3600


def default_send(text: str, *, title: str = "Operator OS") -> bool:
    """Best-effort human notification via existing transports. Never raises.

    Tries ntfy's standalone push first (closest to a phone notification). The
    caller still records the escalation durably, so a False return (no transport)
    is non-fatal.
    """
    try:
        from plugins.platforms.ntfy.adapter import _standalone_send  # type: ignore

        try:
            return bool(_standalone_send(text, title=title))
        except TypeError:
            # Some builds expose a single-arg signature.
            return bool(_standalone_send(text))
    except Exception:
        logger.warning("escalation (no ntfy transport): %s", text)
        return False


class EscalationRouter:
    """Deny-and-escalate router with 24h state-hash dedup.

    Identical (reason, key) escalations inside the window are suppressed so a
    looping mission cannot spam the human with the same blocker.
    """

    def __init__(
        self,
        *,
        send_fn: Optional[Callable[[str], bool]] = None,
        dedup_window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS,
    ) -> None:
        self._send = send_fn or (lambda text: default_send(text))
        self._window = int(dedup_window_seconds)
        self._recent: Dict[str, float] = {}  # state-hash -> last-sent epoch

    @staticmethod
    def _hash(reason: str, key: str) -> str:
        return hashlib.sha256(f"{reason}:{key}".encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def format(reason: str, detail: str) -> str:
        return f"[Operator OS] {reason}: {detail}"

    def escalate(
        self,
        reason: str,
        *,
        detail: str,
        key: str = "",
        now: Optional[float] = None,
    ) -> dict:
        """Send (or suppress) an escalation. Returns a result dict.

        ``key`` scopes dedup (e.g. the missing secret name or the mission id);
        defaults to ``detail``. ``now`` is injectable for tests.
        """
        if reason not in ESCALATION_REASONS:
            raise ValueError(f"unknown escalation reason: {reason!r}")
        ts = time.time() if now is None else float(now)
        h = self._hash(reason, key or detail)
        last = self._recent.get(h)
        if last is not None and (ts - last) < self._window:
            return {"reason": reason, "sent": False, "suppressed": True}
        self._recent[h] = ts
        sent = False
        try:
            sent = bool(self._send(self.format(reason, detail)))
        except Exception:  # a notifier must never crash the loop
            logger.exception("escalation send failed: %s", reason)
        return {"reason": reason, "sent": sent, "suppressed": False}


__all__ = [
    "EscalationRouter",
    "default_send",
    "ESCALATION_REASONS",
    "NEW_SECRET_REQUIRED",
    "PURCHASE",
    "IRREVERSIBLE",
    "PLAN_APPROVAL",
    "BUDGET_CEILING",
    "NO_PROGRESS",
    "DISPATCHER_STUCK",
    "N_DENIALS",
]
