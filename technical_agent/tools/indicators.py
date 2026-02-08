"""Technical indicator calculations."""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from ..config import IndicatorConfig


def compute_indicators(df: pd.DataFrame, config: IndicatorConfig) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    required_cols = {"close", "high", "low", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for indicators: {sorted(missing)}")

    data = df.copy()
    data["returns"] = data["close"].pct_change()

    for period in config.sma_periods:
        data[f"sma_{period}"] = ta.sma(data["close"], length=period)

    for period in config.ema_periods:
        data[f"ema_{period}"] = ta.ema(data["close"], length=period)

    data[f"rsi_{config.rsi_period}"] = ta.rsi(data["close"], length=config.rsi_period)

    macd = ta.macd(
        data["close"],
        fast=config.macd_fast,
        slow=config.macd_slow,
        signal=config.macd_signal,
    )
    if macd is not None and not macd.empty:
        data["macd"] = macd.iloc[:, 0]
        data["macd_signal"] = macd.iloc[:, 1]
        data["macd_hist"] = macd.iloc[:, 2]

    bbands = ta.bbands(
        data["close"], length=config.bb_length, std=config.bb_std
    )
    if bbands is not None and not bbands.empty:
        data["bb_lower"] = bbands.iloc[:, 0]
        data["bb_mid"] = bbands.iloc[:, 1]
        data["bb_upper"] = bbands.iloc[:, 2]

    data[f"atr_{config.atr_period}"] = ta.atr(
        data["high"], data["low"], data["close"], length=config.atr_period
    )

    adx = ta.adx(
        data["high"], data["low"], data["close"], length=config.adx_period
    )
    if adx is not None and not adx.empty:
        data[f"adx_{config.adx_period}"] = adx.iloc[:, 0]
        data[f"plus_di_{config.adx_period}"] = adx.iloc[:, 1]
        data[f"minus_di_{config.adx_period}"] = adx.iloc[:, 2]

    stoch = ta.stoch(
        data["high"],
        data["low"],
        data["close"],
        k=config.stoch_k,
        d=config.stoch_d,
        smooth_k=config.stoch_smooth,
    )
    if stoch is not None and not stoch.empty:
        data["stoch_k"] = stoch.iloc[:, 0]
        data["stoch_d"] = stoch.iloc[:, 1]

    data[f"cci_{config.cci_period}"] = ta.cci(
        data["high"], data["low"], data["close"], length=config.cci_period
    )
    data[f"roc_{config.roc_period}"] = ta.roc(
        data["close"], length=config.roc_period
    )
    data[f"willr_{config.willr_period}"] = ta.willr(
        data["high"], data["low"], data["close"], length=config.willr_period
    )
    data[f"mfi_{config.mfi_period}"] = ta.mfi(
        data["high"],
        data["low"],
        data["close"],
        data["volume"],
        length=config.mfi_period,
    )

    data["obv"] = ta.obv(data["close"], data["volume"])

    volume_mean = data["volume"].rolling(config.volume_zscore_period).mean()
    volume_std = data["volume"].rolling(config.volume_zscore_period).std()
    data["volume_zscore"] = (data["volume"] - volume_mean) / volume_std

    return data
