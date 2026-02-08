"""Built-in technical signals."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd

from ..config import SignalConfig
from ..models import Signal
from .registry import register_signal


def _format_timestamp(index_value: object) -> str:
    if isinstance(index_value, pd.Timestamp):
        return index_value.isoformat()
    return str(index_value)


def _get_last_two_rows(
    df: pd.DataFrame, columns: List[str]
) -> Optional[Tuple[pd.Series, pd.Series]]:
    if any(col not in df.columns for col in columns):
        return None
    subset = df[columns].dropna()
    if len(subset) < 2:
        return None
    return subset.iloc[-2], subset.iloc[-1]


def _parse_period(col: str, prefix: str) -> int:
    try:
        return int(str(col).replace(prefix, "").split("_")[0])
    except (ValueError, TypeError):
        return 0


def _find_period_column(df: pd.DataFrame, prefix: str) -> Optional[str]:
    candidates = [col for col in df.columns if str(col).startswith(prefix)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda c: _parse_period(str(c), prefix))[-1]


def _select_two_period_columns(
    df: pd.DataFrame, prefix: str, preferred: List[str]
) -> Optional[List[str]]:
    if all(col in df.columns for col in preferred):
        return preferred
    candidates = [col for col in df.columns if str(col).startswith(prefix)]
    if len(candidates) < 2:
        return None
    candidates = sorted(candidates, key=lambda c: _parse_period(str(c), prefix))
    return [candidates[0], candidates[1]]


def _build_signal(
    name: str,
    symbol: str,
    timestamp: object,
    direction: str,
    strength: float,
    horizon: str,
    rationale: str,
    indicators: dict,
) -> Signal:
    return Signal(
        name=name,
        symbol=symbol,
        timestamp=_format_timestamp(timestamp),
        direction=direction,
        strength=float(strength),
        horizon=horizon,
        rationale=rationale,
        indicators=indicators,
    )


@register_signal("sma_crossover", "Short/medium SMA crossover.")
def sma_crossover_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = _select_two_period_columns(df, "sma_", ["sma_20", "sma_50"])
    if not cols:
        return []
    rows = _get_last_two_rows(df, cols)
    if rows is None:
        return []
    prev, last = rows
    short_col, long_col = cols
    direction = None
    if prev[short_col] <= prev[long_col] and last[short_col] > last[long_col]:
        direction = "bullish"
    elif prev[short_col] >= prev[long_col] and last[short_col] < last[long_col]:
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last[short_col] - last[long_col]) / max(1e-9, last[long_col])
    return [
        _build_signal(
            name="sma_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="medium",
            rationale=f"SMA crossover detected ({short_col}/{long_col}).",
            indicators={short_col: last[short_col], long_col: last[long_col]},
        )
    ]


@register_signal("ema_crossover", "Short/medium EMA crossover.")
def ema_crossover_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = _select_two_period_columns(df, "ema_", ["ema_12", "ema_26"])
    if not cols:
        return []
    rows = _get_last_two_rows(df, cols)
    if rows is None:
        return []
    prev, last = rows
    short_col, long_col = cols
    direction = None
    if prev[short_col] <= prev[long_col] and last[short_col] > last[long_col]:
        direction = "bullish"
    elif prev[short_col] >= prev[long_col] and last[short_col] < last[long_col]:
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last[short_col] - last[long_col]) / max(1e-9, last[long_col])
    return [
        _build_signal(
            name="ema_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale=f"EMA crossover detected ({short_col}/{long_col}).",
            indicators={short_col: last[short_col], long_col: last[long_col]},
        )
    ]


@register_signal("rsi_extremes", "RSI overbought/oversold levels.")
def rsi_extremes_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    col = _find_period_column(df, "rsi_")
    if col not in df.columns:
        return []
    series = df[col].dropna()
    if series.empty:
        return []
    last = series.iloc[-1]
    ts = series.index[-1]

    if last <= config.rsi_oversold:
        return [
            _build_signal(
                name="rsi_extremes",
                symbol=symbol,
                timestamp=ts,
                direction="bullish",
                strength=min(1.0, (config.rsi_oversold - last) / config.rsi_oversold),
                horizon="short",
                rationale="RSI indicates oversold conditions.",
                indicators={col: last},
            )
        ]
    if last >= config.rsi_overbought:
        return [
            _build_signal(
                name="rsi_extremes",
                symbol=symbol,
                timestamp=ts,
                direction="bearish",
                strength=min(1.0, (last - config.rsi_overbought) / (100 - config.rsi_overbought)),
                horizon="short",
                rationale="RSI indicates overbought conditions.",
                indicators={col: last},
            )
        ]
    return []


@register_signal("macd_crossover", "MACD line crossing signal line.")
def macd_crossover_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    rows = _get_last_two_rows(df, ["macd", "macd_signal", "macd_hist"])
    if rows is None:
        return []
    prev, last = rows
    direction = None
    if prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]:
        direction = "bullish"
    elif prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]:
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last["macd_hist"]) / max(1e-9, abs(last["macd"]))
    return [
        _build_signal(
            name="macd_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="MACD crossover detected.",
            indicators={
                "macd": last["macd"],
                "macd_signal": last["macd_signal"],
                "macd_hist": last["macd_hist"],
            },
        )
    ]


@register_signal("bollinger_band", "Price outside Bollinger Bands.")
def bollinger_band_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = ["close", "bb_lower", "bb_upper"]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    direction = None
    if last["close"] < last["bb_lower"]:
        direction = "bullish"
        rationale = "Price closed below lower Bollinger Band."
    elif last["close"] > last["bb_upper"]:
        direction = "bearish"
        rationale = "Price closed above upper Bollinger Band."
    else:
        return []

    width = max(1e-9, last["bb_upper"] - last["bb_lower"])
    strength = abs(last["close"] - (last["bb_upper"] if direction == "bearish" else last["bb_lower"])) / width

    return [
        _build_signal(
            name="bollinger_band",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale=rationale,
            indicators={
                "close": last["close"],
                "bb_lower": last["bb_lower"],
                "bb_upper": last["bb_upper"],
            },
        )
    ]


@register_signal("stochastic_cross", "Stochastic oscillator cross in extreme zone.")
def stochastic_cross_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    rows = _get_last_two_rows(df, ["stoch_k", "stoch_d"])
    if rows is None:
        return []
    prev, last = rows
    direction = None
    if (
        prev["stoch_k"] <= prev["stoch_d"]
        and last["stoch_k"] > last["stoch_d"]
        and last["stoch_k"] <= config.stoch_oversold
    ):
        direction = "bullish"
    elif (
        prev["stoch_k"] >= prev["stoch_d"]
        and last["stoch_k"] < last["stoch_d"]
        and last["stoch_k"] >= config.stoch_overbought
    ):
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last["stoch_k"] - last["stoch_d"]) / 100.0
    return [
        _build_signal(
            name="stochastic_cross",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="Stochastic crossover in extreme zone.",
            indicators={"stoch_k": last["stoch_k"], "stoch_d": last["stoch_d"]},
        )
    ]


@register_signal("adx_trend", "Directional trend strength from ADX.")
def adx_trend_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    adx_col = _find_period_column(df, "adx_")
    if not adx_col:
        return []
    period = _parse_period(adx_col, "adx_")
    plus_col = f"plus_di_{period}"
    minus_col = f"minus_di_{period}"
    if plus_col not in df.columns:
        plus_col = _find_period_column(df, "plus_di_") or plus_col
    if minus_col not in df.columns:
        minus_col = _find_period_column(df, "minus_di_") or minus_col
    cols = [adx_col, plus_col, minus_col]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    if last[adx_col] < config.adx_trend_threshold:
        return []

    direction = "bullish" if last[plus_col] > last[minus_col] else "bearish"
    strength = min(1.0, last[adx_col] / 50.0)
    return [
        _build_signal(
            name="adx_trend",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=strength,
            horizon="medium",
            rationale="ADX indicates a strong directional trend.",
            indicators={
                adx_col: last[adx_col],
                plus_col: last[plus_col],
                minus_col: last[minus_col],
            },
        )
    ]


@register_signal("volume_spike", "Volume spike with price direction.")
def volume_spike_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = ["volume_zscore", "returns"]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    if last["volume_zscore"] < config.volume_zscore_threshold:
        return []

    if last["returns"] > 0:
        direction = "bullish"
    elif last["returns"] < 0:
        direction = "bearish"
    else:
        direction = "neutral"

    strength = min(1.0, last["volume_zscore"] / 5.0)
    return [
        _build_signal(
            name="volume_spike",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=strength,
            horizon="short",
            rationale="Unusual volume activity detected.",
            indicators={
                "volume_zscore": last["volume_zscore"],
                "returns": last["returns"],
            },
        )
    ]


@register_signal("vwap_crossover", "Price crossing VWAP.")
def vwap_crossover_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    rows = _get_last_two_rows(df, ["close", "vwap"])
    if rows is None:
        return []
    prev, last = rows
    direction = None
    if prev["close"] <= prev["vwap"] and last["close"] > last["vwap"]:
        direction = "bullish"
    elif prev["close"] >= prev["vwap"] and last["close"] < last["vwap"]:
        direction = "bearish"
    if direction is None:
        return []
    strength = abs(last["close"] - last["vwap"]) / max(1e-9, last["vwap"])
    return [
        _build_signal(
            name="vwap_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="Price crossed VWAP.",
            indicators={"close": last["close"], "vwap": last["vwap"]},
        )
    ]


@register_signal("supertrend_flip", "Supertrend direction change.")
def supertrend_flip_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = ["supertrend", "close"]
    if "supertrend_direction" in df.columns:
        rows = _get_last_two_rows(df, ["supertrend_direction", "supertrend", "close"])
        if rows is None:
            return []
        prev, last = rows
        if prev["supertrend_direction"] == last["supertrend_direction"]:
            return []
        direction = "bullish" if last["supertrend_direction"] > 0 else "bearish"
        strength = abs(last["close"] - last["supertrend"]) / max(1e-9, last["close"])
        return [
            _build_signal(
                name="supertrend_flip",
                symbol=symbol,
                timestamp=last.name,
                direction=direction,
                strength=min(1.0, strength),
                horizon="short",
                rationale="Supertrend flipped direction.",
                indicators={
                    "supertrend": last["supertrend"],
                    "supertrend_direction": last["supertrend_direction"],
                    "close": last["close"],
                },
            )
        ]

    rows = _get_last_two_rows(df, cols)
    if rows is None:
        return []
    prev, last = rows
    if prev["close"] <= prev["supertrend"] and last["close"] > last["supertrend"]:
        direction = "bullish"
    elif prev["close"] >= prev["supertrend"] and last["close"] < last["supertrend"]:
        direction = "bearish"
    else:
        return []
    strength = abs(last["close"] - last["supertrend"]) / max(1e-9, last["close"])
    return [
        _build_signal(
            name="supertrend_flip",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="Price crossed Supertrend.",
            indicators={"supertrend": last["supertrend"], "close": last["close"]},
        )
    ]


@register_signal("donchian_breakout", "Price breaking Donchian channel.")
def donchian_breakout_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = ["close", "donchian_lower", "donchian_upper"]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    if last["close"] > last["donchian_upper"]:
        direction = "bullish"
        rationale = "Close above Donchian upper band."
        strength = (last["close"] - last["donchian_upper"]) / max(1e-9, last["close"])
    elif last["close"] < last["donchian_lower"]:
        direction = "bearish"
        rationale = "Close below Donchian lower band."
        strength = (last["donchian_lower"] - last["close"]) / max(1e-9, last["close"])
    else:
        return []
    return [
        _build_signal(
            name="donchian_breakout",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="medium",
            rationale=rationale,
            indicators={
                "close": last["close"],
                "donchian_lower": last["donchian_lower"],
                "donchian_upper": last["donchian_upper"],
            },
        )
    ]


@register_signal("psar_flip", "Parabolic SAR direction change.")
def psar_flip_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    if "psar_direction" in df.columns:
        rows = _get_last_two_rows(df, ["psar_direction", "psar", "close"])
        if rows is None:
            return []
        prev, last = rows
        if prev["psar_direction"] == last["psar_direction"]:
            return []
        direction = "bullish" if last["psar_direction"] > 0 else "bearish"
        strength = abs(last["close"] - last["psar"]) / max(1e-9, last["close"])
        return [
            _build_signal(
                name="psar_flip",
                symbol=symbol,
                timestamp=last.name,
                direction=direction,
                strength=min(1.0, strength),
                horizon="short",
                rationale="Parabolic SAR flipped direction.",
                indicators={
                    "psar": last["psar"],
                    "psar_direction": last["psar_direction"],
                    "close": last["close"],
                },
            )
        ]
    rows = _get_last_two_rows(df, ["psar", "close"])
    if rows is None:
        return []
    prev, last = rows
    if prev["close"] <= prev["psar"] and last["close"] > last["psar"]:
        direction = "bullish"
    elif prev["close"] >= prev["psar"] and last["close"] < last["psar"]:
        direction = "bearish"
    else:
        return []
    strength = abs(last["close"] - last["psar"]) / max(1e-9, last["close"])
    return [
        _build_signal(
            name="psar_flip",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="Price crossed Parabolic SAR.",
            indicators={"psar": last["psar"], "close": last["close"]},
        )
    ]


@register_signal("ichimoku_cloud", "Price position relative to Ichimoku cloud.")
def ichimoku_cloud_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    cols = ["close", "ichimoku_span_a", "ichimoku_span_b"]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    cloud_top = max(last["ichimoku_span_a"], last["ichimoku_span_b"])
    cloud_bottom = min(last["ichimoku_span_a"], last["ichimoku_span_b"])
    if last["close"] > cloud_top:
        direction = "bullish"
        rationale = "Price is above the Ichimoku cloud."
        strength = (last["close"] - cloud_top) / max(1e-9, last["close"])
    elif last["close"] < cloud_bottom:
        direction = "bearish"
        rationale = "Price is below the Ichimoku cloud."
        strength = (cloud_bottom - last["close"]) / max(1e-9, last["close"])
    else:
        return []
    return [
        _build_signal(
            name="ichimoku_cloud",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="medium",
            rationale=rationale,
            indicators={
                "close": last["close"],
                "ichimoku_span_a": last["ichimoku_span_a"],
                "ichimoku_span_b": last["ichimoku_span_b"],
            },
        )
    ]
