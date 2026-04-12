"""Curated liquid mega-cap universe for long/short pilot runs (20 names)."""

from __future__ import annotations

TOP20_TICKERS: list[str] = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "BRK-B",
    "AVGO",
    "LLY",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "MA",
    "JNJ",
    "PG",
    "COST",
    "HD",
    "ORCL",
]


def get_top20_tickers() -> list[str]:
    return list(TOP20_TICKERS)
