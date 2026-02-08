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
    rows = _get_last_two_rows(df, ["sma_20", "sma_50"])
    if rows is None:
        return []
    prev, last = rows
    direction = None
    if prev["sma_20"] <= prev["sma_50"] and last["sma_20"] > last["sma_50"]:
        direction = "bullish"
    elif prev["sma_20"] >= prev["sma_50"] and last["sma_20"] < last["sma_50"]:
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last["sma_20"] - last["sma_50"]) / max(1e-9, last["sma_50"])
    return [
        _build_signal(
            name="sma_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="medium",
            rationale="SMA 20/50 crossover detected.",
            indicators={"sma_20": last["sma_20"], "sma_50": last["sma_50"]},
        )
    ]


@register_signal("ema_crossover", "Short/medium EMA crossover.")
def ema_crossover_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    rows = _get_last_two_rows(df, ["ema_12", "ema_26"])
    if rows is None:
        return []
    prev, last = rows
    direction = None
    if prev["ema_12"] <= prev["ema_26"] and last["ema_12"] > last["ema_26"]:
        direction = "bullish"
    elif prev["ema_12"] >= prev["ema_26"] and last["ema_12"] < last["ema_26"]:
        direction = "bearish"

    if direction is None:
        return []

    strength = abs(last["ema_12"] - last["ema_26"]) / max(1e-9, last["ema_26"])
    return [
        _build_signal(
            name="ema_crossover",
            symbol=symbol,
            timestamp=last.name,
            direction=direction,
            strength=min(1.0, strength),
            horizon="short",
            rationale="EMA 12/26 crossover detected.",
            indicators={"ema_12": last["ema_12"], "ema_26": last["ema_26"]},
        )
    ]


@register_signal("rsi_extremes", "RSI overbought/oversold levels.")
def rsi_extremes_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    col = "rsi_14"
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
    cols = ["adx_14", "plus_di_14", "minus_di_14"]
    if any(col not in df.columns for col in cols):
        return []
    subset = df[cols].dropna()
    if subset.empty:
        return []
    last = subset.iloc[-1]
    if last["adx_14"] < config.adx_trend_threshold:
        return []

    direction = "bullish" if last["plus_di_14"] > last["minus_di_14"] else "bearish"
    strength = min(1.0, last["adx_14"] / 50.0)
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
                "adx_14": last["adx_14"],
                "plus_di_14": last["plus_di_14"],
                "minus_di_14": last["minus_di_14"],
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
