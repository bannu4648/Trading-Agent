"""Data loading tools powered by yfinance."""

from __future__ import annotations

from typing import Dict, Iterable

import pandas as pd
import yfinance as yf


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).lower().replace(" ", "_") for col in df.columns]
    rename_map = {}
    if "adj_close" not in df.columns and "adjclose" in df.columns:
        rename_map["adjclose"] = "adj_close"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def fetch_ohlcv_data(
    tickers: Iterable[str],
    start_date: str | None,
    end_date: str | None,
    interval: str = "1d",
    auto_adjust: bool = True,
    prepost: bool = False,
) -> Dict[str, pd.DataFrame]:
    ticker_list = [t.strip().upper() for t in tickers if t and t.strip()]
    if not ticker_list:
        raise ValueError("At least one ticker is required.")

    data = yf.download(
        tickers=" ".join(ticker_list),
        start=start_date,
        end=end_date,
        interval=interval,
        auto_adjust=auto_adjust,
        prepost=prepost,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    if data.empty:
        return {}

    result: Dict[str, pd.DataFrame] = {}

    if isinstance(data.columns, pd.MultiIndex):
        for ticker in ticker_list:
            if ticker in data.columns.get_level_values(0):
                df = data[ticker].copy()
                df = normalize_ohlcv(df)
                if not df.empty:
                    result[ticker] = df
    else:
        df = normalize_ohlcv(data)
        result[ticker_list[0]] = df

    return result
