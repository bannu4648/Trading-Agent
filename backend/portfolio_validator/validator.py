"""
Portfolio Validator — checks allocation rules before orders go out.

Pure arithmetic, no LLM. Flags things like concentration risk and
too-low cash buffers. Supports long-only and long/short (negative weights).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_SINGLE_WEIGHT = 0.40
_MAX_TOTAL_INVESTED = 0.90
_MAX_GROSS_SHORT = 0.60
_LOW_CONVICTION_FLOOR = 5.0
_LOW_CONVICTION_CAP = 0.20
_HIGH_VOL_THRESHOLD = 0.35
_WEIGHT_EPS = 1e-6


class PortfolioValidator:
    """
    Runs sanity checks on proposed trade orders and returns
    risk_level (LOW / MEDIUM / HIGH) and warnings.

    Positions with abs(proposed_weight) > eps are "active" (includes shorts).
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def validate(
        self,
        orders: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        rec_map = {r["ticker"]: r for r in recommendations}

        active = [
            o for o in orders
            if abs(float(o.get("proposed_weight", 0) or 0)) > _WEIGHT_EPS
        ]
        gross_long = round(
            sum(max(0.0, float(o["proposed_weight"])) for o in active), 4
        )
        gross_short = round(
            sum(max(0.0, -float(o["proposed_weight"])) for o in active), 4
        )
        has_shorts = any(float(o["proposed_weight"]) < -_WEIGHT_EPS for o in active)

        total_invested_long = gross_long
        cash_buffer = round(1.0 - total_invested_long, 4) if not has_shorts else None

        if not has_shorts:
            if total_invested_long > _MAX_TOTAL_INVESTED:
                warnings.append(
                    f"Total long exposure is {total_invested_long:.1%} — cash buffer "
                    f"({cash_buffer:.1%}) is below the {1 - _MAX_TOTAL_INVESTED:.0%} minimum."
                )
        else:
            if gross_long > _MAX_TOTAL_INVESTED:
                warnings.append(
                    f"Gross long exposure is {gross_long:.1%} — above {_MAX_TOTAL_INVESTED:.0%} guideline."
                )
            if gross_short > _MAX_GROSS_SHORT:
                warnings.append(
                    f"Gross short exposure is {gross_short:.1%} — above {_MAX_GROSS_SHORT:.0%} guideline."
                )

        largest = max(active, key=lambda o: abs(float(o["proposed_weight"])), default=None)
        if largest and abs(float(largest["proposed_weight"])) > _MAX_SINGLE_WEIGHT:
            warnings.append(
                f"{largest['ticker']} is {abs(float(largest['proposed_weight'])):.1%} (abs) — "
                f"above the {_MAX_SINGLE_WEIGHT:.0%} concentration limit."
            )

        for order in active:
            rec = rec_map.get(order["ticker"], {})
            conviction = rec.get("conviction_score", 10.0)
            w = float(order["proposed_weight"])
            aw = abs(w)
            if conviction < _LOW_CONVICTION_FLOOR and aw > _LOW_CONVICTION_CAP:
                warnings.append(
                    f"{order['ticker']}: conviction is only {conviction:.1f}/10 "
                    f"but |weight| is {aw:.1%} — consider capping at {_LOW_CONVICTION_CAP:.0%}."
                )

        portfolio_vol = sum(
            abs(float(o["proposed_weight"]))
            * float(rec_map.get(o["ticker"], {}).get("volatility", 0.25))
            for o in active
        )
        if portfolio_vol > _HIGH_VOL_THRESHOLD:
            warnings.append(
                f"Weighted abs-notional × vol is {portfolio_vol:.1%} — "
                f"above the {_HIGH_VOL_THRESHOLD:.0%} threshold."
            )

        if len(active) == 1:
            warnings.append(
                f"Portfolio has only one position ({active[0]['ticker']}). "
                "Very concentrated — no diversification benefit."
            )

        risk_level = "LOW" if not warnings else ("MEDIUM" if len(warnings) <= 2 else "HIGH")

        self.logger.info(
            f"[portfolio_validator] {risk_level} — {len(warnings)} warning(s), "
            f"gross_long={gross_long:.1%}, gross_short={gross_short:.1%}, vol≈{portfolio_vol:.1%}"
        )

        metrics: dict[str, Any] = {
            "gross_long": gross_long,
            "gross_short": gross_short,
            "has_short_positions": has_shorts,
            "weighted_portfolio_volatility": round(portfolio_vol, 4),
            "num_positions": len(active),
            "largest_position": (
                {
                    "ticker": largest["ticker"],
                    "weight": float(largest["proposed_weight"]),
                    "abs_weight": abs(float(largest["proposed_weight"])),
                }
                if largest
                else None
            ),
        }
        if not has_shorts:
            metrics["total_invested"] = total_invested_long
            metrics["cash_buffer"] = cash_buffer

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "metrics": metrics,
        }

    def review(
        self,
        orders: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.validate(orders, recommendations)
