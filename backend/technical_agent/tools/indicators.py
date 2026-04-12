"""Technical indicator calculations."""

from __future__ import annotations

import pandas as pd

from ..config import IndicatorConfig


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.astype("float64")


def _macd(close: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    macd_hist = macd - macd_signal
    return pd.DataFrame({"macd": macd, "macd_signal": macd_signal, "macd_hist": macd_hist})


def _bbands(close: pd.Series, length: int, std: float) -> pd.DataFrame:
    mid = close.rolling(length, min_periods=length).mean()
    sd = close.rolling(length, min_periods=length).std(ddof=0)
    upper = mid + (std * sd)
    lower = mid - (std * sd)
    return pd.DataFrame({"bb_lower": lower, "bb_mid": mid, "bb_upper": upper})


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    tr = _true_range(high, low, close)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.DataFrame:
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr = _atr(high, low, close, length)
    plus_di = 100.0 * (plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr)
    minus_di = 100.0 * (minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr)

    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, pd.NA)).astype(
        "float64"
    )
    adx = dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return pd.DataFrame(
        {f"adx_{length}": adx, f"plus_di_{length}": plus_di, f"minus_di_{length}": minus_di}
    )


def _stoch(
    high: pd.Series, low: pd.Series, close: pd.Series, k: int, d: int, smooth_k: int
) -> pd.DataFrame:
    lowest_low = low.rolling(k, min_periods=k).min()
    highest_high = high.rolling(k, min_periods=k).max()
    raw_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low).replace(0.0, pd.NA)
    smoothed_k = raw_k.rolling(smooth_k, min_periods=smooth_k).mean()
    stoch_d = smoothed_k.rolling(d, min_periods=d).mean()
    return pd.DataFrame({"stoch_k": smoothed_k, "stoch_d": stoch_d})


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    tp = (high + low + close) / 3.0
    sma = tp.rolling(length, min_periods=length).mean()
    mad = (tp - sma).abs().rolling(length, min_periods=length).mean()
    cci = (tp - sma) / (0.015 * mad.replace(0.0, pd.NA))
    return cci.astype("float64")


def _roc(close: pd.Series, length: int) -> pd.Series:
    prev = close.shift(length)
    return (100.0 * (close - prev) / prev.replace(0.0, pd.NA)).astype("float64")


def _willr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    highest_high = high.rolling(length, min_periods=length).max()
    lowest_low = low.rolling(length, min_periods=length).min()
    return (-100.0 * (highest_high - close) / (highest_high - lowest_low).replace(0.0, pd.NA)).astype(
        "float64"
    )


def _mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    tp = (high + low + close) / 3.0
    rmf = tp * volume
    direction = tp.diff()
    pos_mf = rmf.where(direction > 0, 0.0)
    neg_mf = rmf.where(direction < 0, 0.0)
    pos_sum = pos_mf.rolling(length, min_periods=length).sum()
    neg_sum = neg_mf.abs().rolling(length, min_periods=length).sum()
    mfr = pos_sum / neg_sum.replace(0.0, pd.NA)
    mfi = 100.0 - (100.0 / (1.0 + mfr))
    return mfi.astype("float64")


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().fillna(0.0).apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))
    return (direction * volume).cumsum().astype("float64")


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    tp = (high + low + close) / 3.0
    cum_pv = (tp * volume).cumsum()
    cum_v = volume.cumsum().replace(0.0, pd.NA)
    return (cum_pv / cum_v).astype("float64")


def _ichimoku(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    tenkan: int,
    kijun: int,
    senkou: int,
) -> pd.DataFrame:
    tenkan_sen = (high.rolling(tenkan, min_periods=tenkan).max() + low.rolling(tenkan, min_periods=tenkan).min()) / 2.0
    kijun_sen = (high.rolling(kijun, min_periods=kijun).max() + low.rolling(kijun, min_periods=kijun).min()) / 2.0
    span_a = ((tenkan_sen + kijun_sen) / 2.0).shift(senkou)
    span_b = ((high.rolling(senkou, min_periods=senkou).max() + low.rolling(senkou, min_periods=senkou).min()) / 2.0).shift(senkou)
    chikou = close.shift(-senkou)
    return pd.DataFrame(
        {
            "ichimoku_tenkan": tenkan_sen,
            "ichimoku_kijun": kijun_sen,
            "ichimoku_chikou": chikou,
            "ichimoku_span_a": span_a,
            "ichimoku_span_b": span_b,
        }
    )


def _donchian(high: pd.Series, low: pd.Series, length: int) -> pd.DataFrame:
    lower = low.rolling(length, min_periods=length).min()
    upper = high.rolling(length, min_periods=length).max()
    mid = (lower + upper) / 2.0
    return pd.DataFrame({"donchian_lower": lower, "donchian_mid": mid, "donchian_upper": upper})


def _keltner(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int,
    scalar: float,
) -> pd.DataFrame:
    mid = _ema(close, length)
    atr = _atr(high, low, close, length)
    upper = mid + (scalar * atr)
    lower = mid - (scalar * atr)
    return pd.DataFrame({"keltner_lower": lower, "keltner_mid": mid, "keltner_upper": upper})


def _psar(
    high: pd.Series,
    low: pd.Series,
    step: float,
    max_step: float,
) -> pd.DataFrame:
    if high.empty:
        return pd.DataFrame(index=high.index, columns=["psar", "psar_direction"], dtype="float64")

    psar = pd.Series(index=high.index, dtype="float64")
    direction = pd.Series(index=high.index, dtype="float64")

    # initialize with first two bars
    bull = True
    af = step
    ep = high.iloc[0]
    psar.iloc[0] = low.iloc[0]
    direction.iloc[0] = 1.0

    for i in range(1, len(high)):
        prev_psar = psar.iloc[i - 1]
        if bull:
            psar_i = prev_psar + af * (ep - prev_psar)
            psar_i = min(psar_i, low.iloc[i - 1], low.iloc[i])
            if low.iloc[i] < psar_i:
                bull = False
                psar_i = ep
                ep = low.iloc[i]
                af = step
            else:
                if high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af = min(max_step, af + step)
        else:
            psar_i = prev_psar + af * (ep - prev_psar)
            psar_i = max(psar_i, high.iloc[i - 1], high.iloc[i])
            if high.iloc[i] > psar_i:
                bull = True
                psar_i = ep
                ep = high.iloc[i]
                af = step
            else:
                if low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af = min(max_step, af + step)

        psar.iloc[i] = psar_i
        direction.iloc[i] = 1.0 if bull else -1.0

    return pd.DataFrame({"psar": psar, "psar_direction": direction})


def _supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int,
    multiplier: float,
) -> pd.DataFrame:
    atr = _atr(high, low, close, length)
    hl2 = (high + low) / 2.0
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    st = pd.Series(index=close.index, dtype="float64")
    direction = pd.Series(index=close.index, dtype="float64")

    for i in range(len(close)):
        if i == 0:
            st.iloc[i] = upperband.iloc[i]
            direction.iloc[i] = 1.0
            continue

        prev_st = st.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]

        ub = upperband.iloc[i]
        lb = lowerband.iloc[i]

        if prev_dir > 0:
            lb = max(lb, lowerband.iloc[i - 1]) if pd.notna(lowerband.iloc[i - 1]) else lb
            if close.iloc[i] < lb:
                direction.iloc[i] = -1.0
                st.iloc[i] = ub
            else:
                direction.iloc[i] = 1.0
                st.iloc[i] = lb
        else:
            ub = min(ub, upperband.iloc[i - 1]) if pd.notna(upperband.iloc[i - 1]) else ub
            if close.iloc[i] > ub:
                direction.iloc[i] = 1.0
                st.iloc[i] = lb
            else:
                direction.iloc[i] = -1.0
                st.iloc[i] = ub

        if pd.isna(prev_st):
            st.iloc[i] = ub if direction.iloc[i] < 0 else lb

    return pd.DataFrame({"supertrend": st, "supertrend_direction": direction})


def _column_match(df: pd.DataFrame, contains: str) -> pd.Series | None:
    for col in df.columns:
        if contains in str(col):
            return df[col]
    return None


def _first_non_none(*values: pd.Series | None) -> pd.Series | None:
    for value in values:
        if value is not None:
            return value
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
        data[f"sma_{period}"] = _sma(data["close"], length=period)

    for period in config.ema_periods:
        data[f"ema_{period}"] = _ema(data["close"], length=period)

    data[f"rsi_{config.rsi_period}"] = _rsi(data["close"], length=config.rsi_period)

    macd = _macd(
        data["close"], fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal
    )
    data["macd"] = macd["macd"]
    data["macd_signal"] = macd["macd_signal"]
    data["macd_hist"] = macd["macd_hist"]

    bbands = _bbands(data["close"], length=config.bb_length, std=config.bb_std)
    data["bb_lower"] = bbands["bb_lower"]
    data["bb_mid"] = bbands["bb_mid"]
    data["bb_upper"] = bbands["bb_upper"]

    data[f"atr_{config.atr_period}"] = _atr(
        data["high"], data["low"], data["close"], length=config.atr_period
    )

    adx = _adx(data["high"], data["low"], data["close"], length=config.adx_period)
    data[f"adx_{config.adx_period}"] = adx[f"adx_{config.adx_period}"]
    data[f"plus_di_{config.adx_period}"] = adx[f"plus_di_{config.adx_period}"]
    data[f"minus_di_{config.adx_period}"] = adx[f"minus_di_{config.adx_period}"]

    stoch = _stoch(
        data["high"],
        data["low"],
        data["close"],
        k=config.stoch_k,
        d=config.stoch_d,
        smooth_k=config.stoch_smooth,
    )
    data["stoch_k"] = stoch["stoch_k"]
    data["stoch_d"] = stoch["stoch_d"]

    data[f"cci_{config.cci_period}"] = _cci(
        data["high"], data["low"], data["close"], length=config.cci_period
    )
    data[f"roc_{config.roc_period}"] = _roc(data["close"], length=config.roc_period)
    data[f"willr_{config.willr_period}"] = _willr(
        data["high"], data["low"], data["close"], length=config.willr_period
    )
    data[f"mfi_{config.mfi_period}"] = _mfi(
        data["high"],
        data["low"],
        data["close"],
        data["volume"],
        length=config.mfi_period,
    )

    data["obv"] = _obv(data["close"], data["volume"])

    if config.vwap_enabled:
        data["vwap"] = _vwap(data["high"], data["low"], data["close"], data["volume"])

    ichimoku = _ichimoku(
        data["high"],
        data["low"],
        data["close"],
        tenkan=config.ichimoku_tenkan,
        kijun=config.ichimoku_kijun,
        senkou=config.ichimoku_senkou,
    )
    data["ichimoku_tenkan"] = ichimoku["ichimoku_tenkan"]
    data["ichimoku_kijun"] = ichimoku["ichimoku_kijun"]
    data["ichimoku_chikou"] = ichimoku["ichimoku_chikou"]
    data["ichimoku_span_a"] = ichimoku["ichimoku_span_a"]
    data["ichimoku_span_b"] = ichimoku["ichimoku_span_b"]

    supertrend = _supertrend(
        data["high"],
        data["low"],
        data["close"],
        length=config.supertrend_period,
        multiplier=config.supertrend_multiplier,
    )
    data["supertrend"] = supertrend["supertrend"]
    data["supertrend_direction"] = supertrend["supertrend_direction"]

    donchian = _donchian(data["high"], data["low"], length=config.donchian_length)
    data["donchian_lower"] = donchian["donchian_lower"]
    data["donchian_mid"] = donchian["donchian_mid"]
    data["donchian_upper"] = donchian["donchian_upper"]

    keltner = _keltner(
        data["high"],
        data["low"],
        data["close"],
        length=config.keltner_length,
        scalar=config.keltner_scalar,
    )
    data["keltner_lower"] = keltner["keltner_lower"]
    data["keltner_mid"] = keltner["keltner_mid"]
    data["keltner_upper"] = keltner["keltner_upper"]

    psar = _psar(data["high"], data["low"], step=config.psar_step, max_step=config.psar_max_step)
    data["psar"] = psar["psar"]
    data["psar_direction"] = psar["psar_direction"]

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
