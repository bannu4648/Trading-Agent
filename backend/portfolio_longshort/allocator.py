from __future__ import annotations

import math
from dataclasses import dataclass

from trader_agent.models import StockRecommendation


@dataclass(frozen=True)
class LongShortAllocationParams:
    k_long: int = 25
    k_short: int = 25
    gross_long: float = 1.0
    gross_short: float = 0.5
    max_single_long: float = 0.05
    max_single_short: float = 0.03
    min_abs_position: float = 0.002


def _score(rec: StockRecommendation) -> float:
    """
    Higher score => better long candidate.
    Lower score => better short candidate.
    """
    direction = {"BUY": 1.0, "HOLD": 0.0, "SELL": -1.0}.get(rec.signal, 0.0)
    conviction = max(0.0, min(10.0, float(rec.conviction_score))) / 10.0
    vol = max(1e-6, float(rec.volatility))
    exp_ret = float(rec.expected_return)

    # Risk-adjusted signed score. Direction gates the sign so SELLs naturally sink.
    return direction * (0.65 * conviction + 0.35 * (exp_ret / vol))


def allocate_long_short(
    recs: list[StockRecommendation],
    params: LongShortAllocationParams = LongShortAllocationParams(),
) -> dict[str, float]:
    """
    Create target weights that sum to:
      - longs:  +gross_long
      - shorts: -gross_short

    Returns: {ticker: target_weight} (negative weights represent shorts).
    """
    if not recs:
        return {}

    scored = [(r, _score(r)) for r in recs]
    scored.sort(key=lambda x: x[1], reverse=True)

    longs = [r for r, s in scored if s > 0][: max(0, int(params.k_long))]
    shorts = [r for r, s in reversed(scored) if s < 0][: max(0, int(params.k_short))]

    weights: dict[str, float] = {r.ticker: 0.0 for r in recs}

    def build_leg(leg: list[StockRecommendation], gross: float, max_single: float, sign: float) -> dict[str, float]:
        if not leg or gross <= 0:
            return {}
        raw = {}
        total = 0.0
        for r in leg:
            # Use conviction and expected_return magnitude for sizing within the leg.
            conviction = max(0.0, min(10.0, float(r.conviction_score))) / 10.0
            strength = abs(float(r.expected_return)) + 0.01
            vol = max(1e-6, float(r.volatility))
            w = (0.55 * conviction + 0.45 * (strength / vol))
            w = max(0.0, float(w))
            raw[r.ticker] = w
            total += w
        if total <= 0:
            # fallback: equal weights
            equal = gross / len(leg)
            return {r.ticker: sign * min(max_single, equal) for r in leg}

        # Normalise to gross, then cap and re-normalise remaining mass.
        target = {t: (sign * gross * (v / total)) for t, v in raw.items()}
        capped = {t: max(-max_single if sign < 0 else 0.0, min(max_single if sign > 0 else 0.0, w)) for t, w in target.items()}

        # Re-distribute leftover within uncapped names (single pass).
        capped_abs = sum(abs(w) for w in capped.values())
        leftover = max(0.0, gross - capped_abs)
        if leftover > 1e-9:
            room = {t: (max_single - abs(w)) for t, w in capped.items() if (max_single - abs(w)) > 1e-9}
            room_total = sum(room.values())
            if room_total > 0:
                for t, rroom in room.items():
                    capped[t] += sign * leftover * (rroom / room_total)

        return capped

    long_leg = build_leg(longs, gross=params.gross_long, max_single=params.max_single_long, sign=+1.0)
    short_leg = build_leg(shorts, gross=params.gross_short, max_single=params.max_single_short, sign=-1.0)

    for t, w in long_leg.items():
        weights[t] = float(w)
    for t, w in short_leg.items():
        weights[t] = float(w)

    # Drop tiny allocations
    for t, w in list(weights.items()):
        if abs(w) < params.min_abs_position:
            weights[t] = 0.0

    # Final normalisation to exact gross targets (avoid drift from caps/drop).
    long_sum = sum(w for w in weights.values() if w > 0)
    short_sum = -sum(w for w in weights.values() if w < 0)

    if long_sum > 0 and params.gross_long > 0:
        scale = params.gross_long / long_sum
        for t, w in list(weights.items()):
            if w > 0:
                weights[t] = w * scale
    if short_sum > 0 and params.gross_short > 0:
        scale = params.gross_short / short_sum
        for t, w in list(weights.items()):
            if w < 0:
                weights[t] = w * scale

    # Numerical cleanup
    for t in list(weights.keys()):
        if math.isfinite(weights[t]):
            weights[t] = round(float(weights[t]), 6)
        else:
            weights[t] = 0.0

    return weights

