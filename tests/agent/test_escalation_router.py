"""Phase 1: escalation router — reason validation, dedup, transport safety."""

import pytest

from agent.escalation_router import (
    EscalationRouter,
    NEW_SECRET_REQUIRED,
    BUDGET_CEILING,
)


def _recording_router(**kw):
    sent = []
    r = EscalationRouter(send_fn=lambda text: (sent.append(text) or True), **kw)
    return r, sent


def test_unknown_reason_raises():
    r, _ = _recording_router()
    with pytest.raises(ValueError):
        r.escalate("NOT_A_REASON", detail="x", now=0.0)


def test_first_escalation_sends():
    r, sent = _recording_router()
    res = r.escalate(NEW_SECRET_REQUIRED, detail="OPENAI_API_KEY", now=0.0)
    assert res["sent"] is True and res["suppressed"] is False
    assert len(sent) == 1
    assert "NEW_SECRET_REQUIRED" in sent[0] and "OPENAI_API_KEY" in sent[0]


def test_identical_within_window_suppressed():
    r, sent = _recording_router(dedup_window_seconds=24 * 3600)
    r.escalate(NEW_SECRET_REQUIRED, detail="OPENAI_API_KEY", key="OPENAI_API_KEY", now=0.0)
    res = r.escalate(NEW_SECRET_REQUIRED, detail="OPENAI_API_KEY", key="OPENAI_API_KEY", now=3600.0)
    assert res["suppressed"] is True and res["sent"] is False
    assert len(sent) == 1  # only the first went out


def test_resends_after_window():
    r, sent = _recording_router(dedup_window_seconds=100)
    r.escalate(BUDGET_CEILING, detail="cap hit", key="m1", now=0.0)
    res = r.escalate(BUDGET_CEILING, detail="cap hit", key="m1", now=101.0)
    assert res["suppressed"] is False and res["sent"] is True
    assert len(sent) == 2


def test_different_key_not_suppressed():
    r, sent = _recording_router()
    r.escalate(NEW_SECRET_REQUIRED, detail="A", key="A", now=0.0)
    r.escalate(NEW_SECRET_REQUIRED, detail="B", key="B", now=1.0)
    assert len(sent) == 2


def test_transport_failure_does_not_raise():
    def boom(_text):
        raise RuntimeError("notifier down")

    r = EscalationRouter(send_fn=boom)
    res = r.escalate(BUDGET_CEILING, detail="x", now=0.0)
    # Recorded as not-sent, but the call returns cleanly (loop must not crash).
    assert res["sent"] is False and res["suppressed"] is False
