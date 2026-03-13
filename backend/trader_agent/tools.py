"""
LangChain tools available to the Trader Agent.

Each tool accepts a JSON string representing a list of stock recommendations
(matching the StockRecommendation schema) and returns a dict mapping ticker ->
proposed weight (as a decimal fraction of the portfolio).

Tools:
  1. equal_weight               — splits equally among all BUY signals
  2. conviction_weight          — proportional to normalised conviction scores
  3. volatility_adjusted_weight — risk-parity: inversely proportional to volatility
  4. kelly_criterion_weight     — Kelly fraction based on win-prob and payoff
  5. generate_trade_orders      — computes delta orders given targets vs current weights

Portfolio Constraints (Change 3 — FINCON/fractional-Kelly research):
  - MAX_SINGLE_POSITION = 40% (no more than 40% in any one stock)
  - MAX_INVESTED        = 90% (always keep at least 10% cash buffer)
  - These prevent catastrophic losses from overconcentration
"""

from __future__ import annotations

import json
import math

from langchain_core.tools import tool

# Portfolio safety constraints (research-backed)
_MAX_SINGLE_POSITION = 0.40  # Never more than 40% in one stock
_MAX_INVESTED = 0.90          # Always keep ≥10% cash
_MIN_POSITION = 0.005         # Positions below 0.5% are rounded to 0


def _parse_recs(recs_json: str) -> list[dict]:
    """Parse a JSON list of stock recommendation dicts."""
    data = json.loads(recs_json)
    if isinstance(data, dict) and "recommendations" in data:
        return data["recommendations"]
    return data


def _apply_portfolio_constraints(weights: dict[str, float]) -> dict[str, float]:
    """
    Apply portfolio safety constraints inspired by FINCON (NeurIPS 2024)
    and fractional Kelly research:
      1. Cap each position at MAX_SINGLE_POSITION (40%)
      2. Scale total invested to MAX_INVESTED (90%)
      3. Drop positions below MIN_POSITION

    The 10% cash floor acts as a buffer for:
    - Exploiting sudden dip opportunities
    - Covering transaction costs/slippage
    - Risk management (never go fully invested)
    """
    if not weights:
        return weights

    # Step 1: cap each position at 40%
    capped = {k: min(v, _MAX_SINGLE_POSITION) for k, v in weights.items()}

    # Step 2: rescale so total invested ≤ 90%
    total = sum(capped.values())
    if total > _MAX_INVESTED:
        scale = _MAX_INVESTED / total
        capped = {k: round(v * scale, 6) for k, v in capped.items()}
    elif total > 0:
        # Already under the cap — just round
        capped = {k: round(v, 6) for k, v in capped.items()}

    # Step 3: drop tiny positions (noise)
    capped = {k: (v if v >= _MIN_POSITION else 0.0) for k, v in capped.items()}

    return capped


@tool
def equal_weight(recommendations_json: str) -> str:
    """
    Calculate equal-weight position sizes for all BUY-signal stocks.

    Splits investable capital equally across every stock with a BUY signal.
    Applies portfolio safety constraints: max 40% per stock, max 90% total.
    SELL and HOLD signals receive a target weight of 0.

    Args:
        recommendations_json: JSON string — a list of stock recommendation objects,
            each with fields: ticker, signal, conviction_score, expected_return,
            volatility, current_weight.

    Returns:
        JSON string mapping ticker -> proposed_weight (decimal fraction).
    """
    recs = _parse_recs(recommendations_json)
    buys = [r for r in recs if r.get("signal") == "BUY"]
    weights: dict[str, float] = {}

    if not buys:
        for r in recs:
            weights[r["ticker"]] = 0.0
        return json.dumps({"method": "equal_weight", "weights": weights})

    equal_share = min(1.0 / len(buys), _MAX_SINGLE_POSITION)
    for r in recs:
        weights[r["ticker"]] = round(equal_share, 6) if r.get("signal") == "BUY" else 0.0

    weights = _apply_portfolio_constraints(weights)
    return json.dumps({"method": "equal_weight", "weights": weights})


@tool
def conviction_weight(recommendations_json: str) -> str:
    """
    Calculate conviction-weighted position sizes for all BUY-signal stocks.

    Weights each BUY stock proportionally to its conviction score.
    Applies portfolio safety constraints: max 40% per stock, max 90% total.
    SELL and HOLD signals receive a target weight of 0.

    Args:
        recommendations_json: JSON string — a list of stock recommendation objects,
            each with fields: ticker, signal, conviction_score, expected_return,
            volatility, current_weight.

    Returns:
        JSON string mapping ticker -> proposed_weight (decimal fraction).
    """
    recs = _parse_recs(recommendations_json)
    buys = [r for r in recs if r.get("signal") == "BUY"]
    weights: dict[str, float] = {}

    if not buys:
        for r in recs:
            weights[r["ticker"]] = 0.0
        return json.dumps({"method": "conviction_weight", "weights": weights})

    total_conviction = sum(r["conviction_score"] for r in buys)
    for r in recs:
        if r.get("signal") == "BUY" and total_conviction > 0:
            weights[r["ticker"]] = round(r["conviction_score"] / total_conviction, 6)
        else:
            weights[r["ticker"]] = 0.0

    weights = _apply_portfolio_constraints(weights)
    return json.dumps({"method": "conviction_weight", "weights": weights})


@tool
def volatility_adjusted_weight(recommendations_json: str) -> str:
    """
    Calculate risk-parity (volatility-adjusted) position sizes for BUY-signal stocks.

    Sizes each BUY position inversely proportional to its annualised volatility,
    so that every position contributes approximately equal risk to the portfolio.
    SELL and HOLD signals receive a target weight of 0.

    Args:
        recommendations_json: JSON string — a list of stock recommendation objects,
            each with fields: ticker, signal, conviction_score, expected_return,
            volatility, current_weight.

    Returns:
        JSON string mapping ticker -> proposed_weight (decimal fraction).
    """
    recs = _parse_recs(recommendations_json)
    buys = [r for r in recs if r.get("signal") == "BUY"]
    weights: dict[str, float] = {}

    if not buys:
        for r in recs:
            weights[r["ticker"]] = 0.0
        return json.dumps({"method": "volatility_adjusted_weight", "weights": weights})

    inv_vols = {r["ticker"]: 1.0 / r["volatility"] for r in buys if r["volatility"] > 0}
    total_inv_vol = sum(inv_vols.values())

    for r in recs:
        if r.get("signal") == "BUY" and r["ticker"] in inv_vols and total_inv_vol > 0:
            weights[r["ticker"]] = round(inv_vols[r["ticker"]] / total_inv_vol, 6)
        else:
            weights[r["ticker"]] = 0.0

    weights = _apply_portfolio_constraints(weights)
    return json.dumps({"method": "volatility_adjusted_weight", "weights": weights})


@tool
def kelly_criterion_weight(recommendations_json: str) -> str:
    """
    Calculate Kelly Criterion position sizes for BUY-signal stocks.

    Kelly fraction f* = (p * b - q) / b, where:
      - p = probability of winning, derived from conviction_score / 10
      - q = 1 - p (probability of losing)
      - b = expected_return / assumed_loss (payoff ratio, assumed_loss = 0.10)

    Raw Kelly fractions are half-Kelly capped (multiplied by 0.5) to reduce
    volatility, and negative fractions are floored at 0.
    Final weights are normalised to sum to 1.0.
    SELL and HOLD signals receive a target weight of 0.

    Args:
        recommendations_json: JSON string — a list of stock recommendation objects,
            each with fields: ticker, signal, conviction_score, expected_return,
            volatility, current_weight.

    Returns:
        JSON string mapping ticker -> proposed_weight (decimal fraction).
    """
    ASSUMED_LOSS = 0.10
    HALF_KELLY = 0.5

    recs = _parse_recs(recommendations_json)
    buys = [r for r in recs if r.get("signal") == "BUY"]
    weights: dict[str, float] = {}

    if not buys:
        for r in recs:
            weights[r["ticker"]] = 0.0
        return json.dumps({"method": "kelly_criterion_weight", "weights": weights})

    raw_kelly: dict[str, float] = {}
    for r in buys:
        p = r["conviction_score"] / 10.0
        q = 1.0 - p
        b = r["expected_return"] / ASSUMED_LOSS if ASSUMED_LOSS > 0 else 1.0
        if b <= 0:
            raw_kelly[r["ticker"]] = 0.0
        else:
            f = (p * b - q) / b
            raw_kelly[r["ticker"]] = max(0.0, f * HALF_KELLY)

    total_kelly = sum(raw_kelly.values())

    for r in recs:
        if r.get("signal") == "BUY" and total_kelly > 0:
            weights[r["ticker"]] = round(raw_kelly.get(r["ticker"], 0.0) / total_kelly, 6)
        else:
            weights[r["ticker"]] = 0.0

    weights = _apply_portfolio_constraints(weights)
    return json.dumps({
        "method": "kelly_criterion_weight",
        "weights": weights,
        "raw_kelly_fractions": {k: round(v, 6) for k, v in raw_kelly.items()},
    })


@tool
def generate_trade_orders(weights_json: str, recommendations_json: str) -> str:
    """
    Generate concrete trade orders by comparing proposed target weights to current weights.

    Action logic:
      delta > 0   → BUY   (open or increase position)
      delta < 0   → SELL  (reduce or close position)
      delta == 0  → HOLD  (no change; when current_weight is 0 this also means
                           "do not open a position" for bearish/neutral signals)

    Args:
        weights_json: JSON string — output from one of the sizing tools, containing
            a 'weights' dict mapping ticker -> proposed_weight.
        recommendations_json: JSON string — the original list of stock recommendation
            objects (needed to read current_weight and signal for each stock).

    Returns:
        JSON string — a list of trade order objects, each with fields:
            ticker, action, proposed_weight, weight_delta, sizing_method_used.
    """
    sizing_result = json.loads(weights_json)
    proposed = sizing_result.get("weights", {})
    method = sizing_result.get("method", "unknown")

    recs = _parse_recs(recommendations_json)
    current_weights = {r["ticker"]: r.get("current_weight", 0.0) for r in recs}
    signals = {r["ticker"]: r.get("signal", "HOLD") for r in recs}

    orders = []
    for ticker, target in proposed.items():
        current = current_weights.get(ticker, 0.0)
        delta = round(target - current, 6)
        signal = signals.get(ticker, "HOLD")

        if delta > 1e-6:
            action = "BUY"
        elif delta < -1e-6:
            action = "SELL"
        else:
            action = "HOLD"

        orders.append({
            "ticker": ticker,
            "action": action,
            "proposed_weight": round(target, 6),
            "weight_delta": delta,
            "sizing_method_used": method,
        })

    total_invested = round(sum(o["proposed_weight"] for o in orders), 6)

    return json.dumps({
        "orders": orders,
        "total_invested_pct": total_invested,
        "sizing_method_used": method,
    })
