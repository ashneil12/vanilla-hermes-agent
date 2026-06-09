"""Per-session spend ceiling for the agent loop (Operator OS mission mode).

Mirrors :class:`IterationBudget`'s simplicity but bounds *spend* (tokens /
dollars) instead of iteration count.  Default-disabled (``None`` ceilings) so a
normal Hermes instance is unaffected; the autonomous profile sets real ceilings
via the ``mission.cost`` config block.

Token-primary by design.  Owned / subscription model routes report cost as
``included``/``unknown`` (``estimate_usage_cost`` returns ``amount_usd=None``,
so ``agent.session_estimated_cost_usd`` stays ``0.0``).  A dollar-only ceiling
would therefore be a no-op on exactly the routes the Operator OS agent runs on,
so the **token** ceiling is the real guard; the dollar ceiling is enforced only
when a real dollar amount is actually accumulating.

The object holds only the ceilings — current spend is read live from the
agent's ``session_total_tokens`` / ``session_estimated_cost_usd`` counters, so
there is nothing to keep in sync.
"""

from __future__ import annotations

from typing import Optional


class CostBudget:
    """Hard spend ceiling for one agent session.

    A budget stop is a HARD stop (no grace iteration): once cumulative session
    spend crosses a ceiling, the agent loop must not make another paid call.
    """

    def __init__(
        self,
        token_ceiling: Optional[int] = None,
        usd_ceiling: Optional[float] = None,
    ) -> None:
        # Treat 0 / negative / falsy as "disabled" so an unset config key or a
        # 0 placeholder can never wedge a loop at the first iteration.
        self.token_ceiling: Optional[int] = (
            int(token_ceiling) if token_ceiling and token_ceiling > 0 else None
        )
        self.usd_ceiling: Optional[float] = (
            float(usd_ceiling) if usd_ceiling and usd_ceiling > 0 else None
        )

    @property
    def enabled(self) -> bool:
        return self.token_ceiling is not None or self.usd_ceiling is not None

    def exceeded(self, tokens_spent: int, usd_spent: float) -> bool:
        """True if cumulative session spend has reached either ceiling."""
        if self.token_ceiling is not None and tokens_spent >= self.token_ceiling:
            return True
        if self.usd_ceiling is not None and usd_spent >= self.usd_ceiling:
            return True
        return False

    def status(self, tokens_spent: int, usd_spent: float) -> str:
        parts = []
        if self.token_ceiling is not None:
            parts.append(f"tokens {tokens_spent}/{self.token_ceiling}")
        if self.usd_ceiling is not None:
            parts.append(f"${usd_spent:.2f}/${self.usd_ceiling:.2f}")
        return ", ".join(parts) or "disabled"

    @classmethod
    def from_config(cls, cost_cfg: Optional[dict] = None) -> "CostBudget":
        if not cost_cfg:
            return cls()
        return cls(
            token_ceiling=cost_cfg.get("token_ceiling"),
            usd_ceiling=cost_cfg.get("usd_ceiling"),
        )

    @classmethod
    def disabled(cls) -> "CostBudget":
        return cls()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"CostBudget(token_ceiling={self.token_ceiling}, usd_ceiling={self.usd_ceiling})"


__all__ = ["CostBudget"]
