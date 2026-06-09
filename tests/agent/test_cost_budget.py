"""Unit tests for the Operator OS mission-mode CostBudget (Phase 0a)."""

from agent.cost_budget import CostBudget


def test_disabled_never_exceeds():
    b = CostBudget()
    assert b.enabled is False
    assert b.exceeded(10**9, 10**9) is False


def test_token_ceiling_bites_at_or_above():
    b = CostBudget(token_ceiling=1000)
    assert b.enabled is True
    assert b.exceeded(999, 0.0) is False
    assert b.exceeded(1000, 0.0) is True
    assert b.exceeded(1001, 0.0) is True


def test_usd_ceiling_bites_at_or_above():
    b = CostBudget(usd_ceiling=2.0)
    assert b.exceeded(0, 1.99) is False
    assert b.exceeded(0, 2.0) is True


def test_token_primary_when_usd_is_included_zero():
    # Owned/subscription route: estimate_usage_cost returns amount_usd=None so
    # session_estimated_cost_usd stays 0.0. The token ceiling MUST still bite.
    b = CostBudget(token_ceiling=500, usd_ceiling=2.0)
    assert b.exceeded(500, 0.0) is True


def test_zero_or_negative_ceiling_treated_as_off():
    assert CostBudget(token_ceiling=0).enabled is False
    assert CostBudget(usd_ceiling=0.0).enabled is False
    assert CostBudget(token_ceiling=-5).enabled is False
    assert CostBudget(token_ceiling=0).exceeded(10**9, 10**9) is False


def test_from_config():
    b = CostBudget.from_config({"token_ceiling": 100, "usd_ceiling": None})
    assert b.token_ceiling == 100
    assert b.usd_ceiling is None
    assert CostBudget.from_config({}).enabled is False
    assert CostBudget.from_config(None).enabled is False


def test_status_string():
    b = CostBudget(token_ceiling=1000, usd_ceiling=2.0)
    s = b.status(500, 1.0)
    assert "tokens 500/1000" in s
    assert "$1.00/$2.00" in s
    assert CostBudget().status(5, 5.0) == "disabled"
