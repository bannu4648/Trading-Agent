"""Integration schema helpers for other agent teams."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .utils.serialization import to_serializable


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_levels(values: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    support_keys = [
        "pivot_s1",
        "pivot_s2",
        "donchian_lower",
        "keltner_lower",
        "bb_lower",
    ]
    resistance_keys = [
        "pivot_r1",
        "pivot_r2",
        "donchian_upper",
        "keltner_upper",
        "bb_upper",
    ]

    support = [_safe_float(values.get(k)) for k in support_keys]
    resistance = [_safe_float(values.get(k)) for k in resistance_keys]

    support_levels = sorted({v for v in support if v is not None})
    resistance_levels = sorted({v for v in resistance if v is not None})
    return support_levels, resistance_levels


def _derive_trend(values: Dict[str, Any]) -> Tuple[str, float]:
    close = _safe_float(values.get("close")) or _safe_float(values.get("adj_close"))
    if close is None:
        return "neutral", 0.0

    ema_short = _safe_float(values.get("ema_12"))
    ema_long = _safe_float(values.get("ema_26"))
    if ema_short is not None and ema_long is not None:
        diff = ema_short - ema_long
        strength = min(1.0, abs(diff) / max(1e-9, close))
        return ("bullish" if diff > 0 else "bearish" if diff < 0 else "neutral"), strength

    sma_short = _safe_float(values.get("sma_20"))
    sma_long = _safe_float(values.get("sma_50"))
    if sma_short is not None and sma_long is not None:
        diff = sma_short - sma_long
        strength = min(1.0, abs(diff) / max(1e-9, close))
        return ("bullish" if diff > 0 else "bearish" if diff < 0 else "neutral"), strength

    supertrend_dir = _safe_float(values.get("supertrend_direction"))
    if supertrend_dir is not None:
        direction = "bullish" if supertrend_dir > 0 else "bearish" if supertrend_dir < 0 else "neutral"
        return direction, min(1.0, abs(supertrend_dir))

    return "neutral", 0.0


def _summarize_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    bullish = sum(1 for s in signals if s.get("direction") == "bullish")
    bearish = sum(1 for s in signals if s.get("direction") == "bearish")
    neutral = sum(1 for s in signals if s.get("direction") == "neutral")

    def _strength(signal: Dict[str, Any]) -> float:
        try:
            return float(signal.get("strength", 0.0))
        except (TypeError, ValueError):
            return 0.0

    top_signals = sorted(signals, key=_strength, reverse=True)[:3]

    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "top_signals": top_signals,
    }


def build_handoff_payload(output: Dict[str, Any]) -> Dict[str, Any]:
    metadata = output.get("metadata", {})
    request = output.get("request", {})
    tickers = output.get("tickers", {})

    handoff: Dict[str, Any] = {
        "schema_version": "1.0",
        "agent": "technical_analyst",
        "generated_at": metadata.get("generated_at"),
        "request": request,
        "tickers": {},
    }

    for symbol, payload in tickers.items():
        indicator_values = payload.get("indicators", {}).get("values", {})
        indicator_values = to_serializable(indicator_values)
        signals = payload.get("signals", [])
        support, resistance = _extract_levels(indicator_values)
        trend, trend_strength = _derive_trend(indicator_values)
        signal_summary = _summarize_signals(signals)

        handoff["tickers"][symbol] = {
            "latest_price": _safe_float(indicator_values.get("close"))
            or _safe_float(indicator_values.get("adj_close")),
            "trend": trend,
            "trend_strength": trend_strength,
            "support_levels": support,
            "resistance_levels": resistance,
            "signal_summary": signal_summary,
            "indicator_snapshot": indicator_values,
            "summary": payload.get("summary", ""),
        }

    return handoff
