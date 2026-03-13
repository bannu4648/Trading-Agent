"""
Portfolio Validator — checks allocation rules before orders go out.

Pure arithmetic, no LLM. Flags things like concentration risk and
too-low cash buffers. Not a proper risk model (VaR/CVaR/stress-testing
will be a separate module later).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Thresholds — these came from the FINCON paper + fractional Kelly research.
# Tweak here if we want to be more/less conservative.
_MAX_SINGLE_WEIGHT   = 0.40   # no single stock should dominate the portfolio
_MAX_TOTAL_INVESTED  = 0.90   # always keep at least 10% as dry powder
_LOW_CONVICTION_FLOOR = 5.0   # below this conviction score, flag big weights
_LOW_CONVICTION_CAP  = 0.20   # if conviction is low, don't allocate more than this
_HIGH_VOL_THRESHOLD  = 0.35   # weighted portfolio vol above this starts to feel risky


class PortfolioValidator:
    """
    Runs a set of sanity checks on proposed trade orders and returns
    a structured report with a risk level (LOW / MEDIUM / HIGH) and
    human-readable warnings.

    Checks:
      1. Total invested ≤ 90%
      2. No single position > 40%
      3. Low-conviction picks aren't over-allocated
      4. Weighted portfolio volatility ≤ 35%
      5. Not a single-stock portfolio
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def validate(
        self,
        orders: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Args:
            orders: trade order dicts (from generate_trade_orders)
            recommendations: stock rec dicts (from adapter)

        Returns a dict with keys: risk_level, warnings, metrics
        """
        warnings: list[str] = []
        rec_map = {r["ticker"]: r for r in recommendations}

        active = [o for o in orders if o.get("proposed_weight", 0) > 0]
        total_invested = round(sum(o["proposed_weight"] for o in active), 4)
        cash_buffer = round(1.0 - total_invested, 4)

        # --- Check 1: too much invested overall ---
        if total_invested > _MAX_TOTAL_INVESTED:
            warnings.append(
                f"Total invested is {total_invested:.1%} — cash buffer ({cash_buffer:.1%}) "
                f"is below the {1 - _MAX_TOTAL_INVESTED:.0%} minimum."
            )

        # --- Check 2: single stock dominating ---
        largest = max(active, key=lambda o: o["proposed_weight"], default=None)
        if largest and largest["proposed_weight"] > _MAX_SINGLE_WEIGHT:
            warnings.append(
                f"{largest['ticker']} is {largest['proposed_weight']:.1%} of portfolio — "
                f"above the {_MAX_SINGLE_WEIGHT:.0%} concentration limit."
            )

        # --- Check 3: low conviction but high weight ---
        for order in active:
            rec = rec_map.get(order["ticker"], {})
            conviction = rec.get("conviction_score", 10.0)
            weight = order["proposed_weight"]
            if conviction < _LOW_CONVICTION_FLOOR and weight > _LOW_CONVICTION_CAP:
                warnings.append(
                    f"{order['ticker']}: conviction is only {conviction:.1f}/10 "
                    f"but it's allocated {weight:.1%} — consider capping at {_LOW_CONVICTION_CAP:.0%}."
                )

        # --- Check 4: portfolio vol getting too high ---
        portfolio_vol = sum(
            o["proposed_weight"] * rec_map.get(o["ticker"], {}).get("volatility", 0.25)
            for o in active
        )
        if portfolio_vol > _HIGH_VOL_THRESHOLD:
            warnings.append(
                f"Weighted portfolio volatility is {portfolio_vol:.1%} — "
                f"above the {_HIGH_VOL_THRESHOLD:.0%} threshold. Consider trimming positions."
            )

        # --- Check 5: all eggs in one basket ---
        if len(active) == 1:
            warnings.append(
                f"Portfolio has only one position ({active[0]['ticker']}). "
                "Very concentrated — no diversification benefit."
            )

        risk_level = "LOW" if not warnings else ("MEDIUM" if len(warnings) <= 2 else "HIGH")

        self.logger.info(
            f"[portfolio_validator] {risk_level} — {len(warnings)} warning(s), "
            f"invested={total_invested:.1%}, vol={portfolio_vol:.1%}"
        )

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "metrics": {
                "total_invested": total_invested,
                "cash_buffer": cash_buffer,
                "largest_position": (
                    {"ticker": largest["ticker"], "weight": largest["proposed_weight"]}
                    if largest else None
                ),
                "weighted_portfolio_volatility": round(portfolio_vol, 4),
                "num_positions": len(active),
            },
        }

    # keep "review" as an alias so old call sites don't break
    def review(
        self,
        orders: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.validate(orders, recommendations)
