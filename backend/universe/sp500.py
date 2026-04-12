from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# Wikipedia lists 503 lines (share classes); reject tiny caches / bad files.
_MIN_SP500_TICKERS = 400


def _default_cache_path() -> Path:
    return Path(__file__).resolve().parent / "cache" / "sp500.json"


def _bundled_constituents_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "sp500_constituents.json"


def _read_bundled_tickers() -> list[str] | None:
    path = _bundled_constituents_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        tickers = [str(t).strip().upper().replace(".", "-") for t in payload.get("tickers", []) if str(t).strip()]
        tickers = [t for t in tickers if t]
        if len(tickers) < _MIN_SP500_TICKERS:
            return None
        return tickers
    except Exception as exc:
        logger.warning("Bundled S&P 500 list unreadable: %s", exc)
        return None


def get_sp500_tickers(
    cache_path: str | None = None,
    max_cache_age_days: int = 7,
) -> list[str]:
    """
    Fetch S&P 500 constituents from Wikipedia and cache them locally.
    Falls back to stale cache, then a **bundled** snapshot in ``data/sp500_constituents.json``,
    so offline / SSL failures still get ~503 names (not a 10-ticker placeholder).
    """
    cache = Path(cache_path) if cache_path else _default_cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)

    def read_cache(*, require_fresh: bool) -> list[str] | None:
        if not cache.exists():
            return None
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            if require_fresh:
                generated_at = datetime.fromisoformat(payload["generated_at"])
                age = datetime.now(timezone.utc) - generated_at
                if age > timedelta(days=max_cache_age_days):
                    return None
            tickers = [str(t).upper().replace(".", "-") for t in payload.get("tickers", []) if str(t).strip()]
            tickers = [t for t in tickers if t]
            if len(tickers) < _MIN_SP500_TICKERS:
                logger.warning(
                    "Ignoring S&P cache at %s (%s tickers); expected at least %s",
                    cache,
                    len(tickers),
                    _MIN_SP500_TICKERS,
                )
                return None
            return tickers
        except Exception as exc:
            logger.warning("S&P cache read failed (%s): %s", cache, exc)
            return None

    fresh = read_cache(require_fresh=True)
    if fresh:
        return fresh

    try:
        resp = requests.get(_WIKI_URL, timeout=20, headers={"User-Agent": "Trading-Agent/1.0"})
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        if not tables:
            raise ValueError("No tables found on Wikipedia page")

        df = tables[0]
        symbol_col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        tickers = [str(x).strip().upper().replace(".", "-") for x in df[symbol_col].tolist()]
        tickers = [t for t in tickers if t]
        if len(tickers) < _MIN_SP500_TICKERS:
            raise ValueError(f"Parsed only {len(tickers)} symbols from Wikipedia")

        cache.write_text(
            json.dumps(
                {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers": tickers},
                indent=2,
            ),
            encoding="utf-8",
        )
        return tickers
    except Exception as exc:
        logger.warning("S&P 500 Wikipedia fetch failed: %s", exc)

    stale = read_cache(require_fresh=False)
    if stale:
        logger.info("Using stale S&P cache (%s tickers) → %s", len(stale), cache)
        return stale

    bundled = _read_bundled_tickers()
    if bundled:
        logger.warning(
            "Using bundled S&P 500 snapshot (%s tickers) from %s",
            len(bundled),
            _bundled_constituents_path(),
        )
        return bundled

    logger.error("No valid S&P 500 source; using minimal emergency list")
    return ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "JPM", "UNH", "XOM"]
