"""Technical indicator calculations."""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from ..config import IndicatorConfig


def _column_match(df: pd.DataFrame, contains: str) -> pd.Series | None:
    for col in df.columns:
        if contains in str(col):
            return df[col]
    return None


def compute_indicators(
    df: pd.DataFrame, config: IndicatorConfig, interval: str = "1d"
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    config = config.for_interval(interval)

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

    if config.vwap_enabled:
        data["vwap"] = ta.vwap(
            data["high"], data["low"], data["close"], data["volume"]
        )

    ichimoku = ta.ichimoku(
        data["high"],
        data["low"],
        data["close"],
        tenkan=config.ichimoku_tenkan,
        kijun=config.ichimoku_kijun,
        senkou=config.ichimoku_senkou,
    )
    if ichimoku is not None:
        if isinstance(ichimoku, tuple):
            ichi_df = ichimoku[0]
            span_df = ichimoku[1] if len(ichimoku) > 1 else None
        else:
            ichi_df = ichimoku
            span_df = None
        if ichi_df is not None and not ichi_df.empty:
            data["ichimoku_tenkan"] = ichi_df.iloc[:, 0]
            if ichi_df.shape[1] > 1:
                data["ichimoku_kijun"] = ichi_df.iloc[:, 1]
            if ichi_df.shape[1] > 2:
                data["ichimoku_chikou"] = ichi_df.iloc[:, 2]
        if span_df is not None and not span_df.empty:
            data["ichimoku_span_a"] = span_df.iloc[:, 0]
            if span_df.shape[1] > 1:
                data["ichimoku_span_b"] = span_df.iloc[:, 1]

    supertrend = ta.supertrend(
        data["high"],
        data["low"],
        data["close"],
        length=config.supertrend_period,
        multiplier=config.supertrend_multiplier,
    )
    if supertrend is not None and not supertrend.empty:
        sup = _column_match(supertrend, "SUPERT_") or supertrend.iloc[:, 0]
        sup_dir = _column_match(supertrend, "SUPERTd") or (
            supertrend.iloc[:, 1] if supertrend.shape[1] > 1 else None
        )
        data["supertrend"] = sup
        if sup_dir is not None:
            data["supertrend_direction"] = sup_dir

    donchian = ta.donchian(
        data["high"], data["low"], length=config.donchian_length
    )
    if donchian is not None and not donchian.empty:
        dcl = _column_match(donchian, "DCL") or donchian.iloc[:, 0]
        dcm = _column_match(donchian, "DCM") or (
            donchian.iloc[:, 1] if donchian.shape[1] > 1 else None
        )
        dch = _column_match(donchian, "DCH") or (
            donchian.iloc[:, 2] if donchian.shape[1] > 2 else None
        )
        data["donchian_lower"] = dcl
        if dcm is not None:
            data["donchian_mid"] = dcm
        if dch is not None:
            data["donchian_upper"] = dch

    keltner = ta.kc(
        data["high"],
        data["low"],
        data["close"],
        length=config.keltner_length,
        scalar=config.keltner_scalar,
    )
    if keltner is not None and not keltner.empty:
        kcl = _column_match(keltner, "KCL") or keltner.iloc[:, 0]
        kcm = _column_match(keltner, "KCB") or (
            keltner.iloc[:, 1] if keltner.shape[1] > 1 else None
        )
        kcu = _column_match(keltner, "KCU") or (
            keltner.iloc[:, 2] if keltner.shape[1] > 2 else None
        )
        data["keltner_lower"] = kcl
        if kcm is not None:
            data["keltner_mid"] = kcm
        if kcu is not None:
            data["keltner_upper"] = kcu

    psar = ta.psar(
        data["high"],
        data["low"],
        data["close"],
        step=config.psar_step,
        max_step=config.psar_max_step,
    )
    if psar is not None and not psar.empty:
        psar_l = _column_match(psar, "PSARl")
        psar_s = _column_match(psar, "PSARs")
        if psar_l is not None or psar_s is not None:
            data["psar"] = (psar_l if psar_l is not None else psar_s).combine_first(
                psar_s if psar_s is not None else psar_l
            )
            if psar_l is not None and psar_s is not None:
                direction = pd.Series(index=psar.index, dtype="float64")
                direction[psar_l.notna()] = 1.0
                direction[psar_s.notna()] = -1.0
                data["psar_direction"] = direction

    if config.pivot_lookback >= 1:
        shift = int(config.pivot_lookback)
        prev_high = data["high"].shift(shift)
        prev_low = data["low"].shift(shift)
        prev_close = data["close"].shift(shift)
        pivot = (prev_high + prev_low + prev_close) / 3.0
        data["pivot"] = pivot
        data["pivot_r1"] = (2 * pivot) - prev_low
        data["pivot_s1"] = (2 * pivot) - prev_high
        data["pivot_r2"] = pivot + (prev_high - prev_low)
        data["pivot_s2"] = pivot - (prev_high - prev_low)

    volume_mean = data["volume"].rolling(config.volume_zscore_period).mean()
    volume_std = data["volume"].rolling(config.volume_zscore_period).std()
    data["volume_zscore"] = (data["volume"] - volume_mean) / volume_std

    return data
