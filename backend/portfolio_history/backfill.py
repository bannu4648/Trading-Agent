from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
import yfinance as yf

from portfolio_history.store import get_latest_row, upsert_paper_daily_row


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _iter_weekdays(start_exclusive: date, end_inclusive: date) -> List[date]:
    out: List[date] = []
    d = start_exclusive + timedelta(days=1)
    while d <= end_inclusive:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _extract_close_panel(raw: pd.DataFrame, tickers: List[str]) -> Dict[str, Dict[str, float]]:
    by_day: Dict[str, Dict[str, float]] = {}
    if raw is None or raw.empty:
        return by_day

    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance multi-ticker format is usually [ticker, field]
        for t in tickers:
            try:
                close_series = raw[t]["Close"]
            except Exception:
                continue
            for ts, px in close_series.dropna().items():
                d = ts.date().isoformat()
                by_day.setdefault(d, {})[t] = float(px)
        return by_day

    # Single ticker can come back as flat columns.
    if len(tickers) != 1:
        return by_day
    t = tickers[0]
    if "Close" not in raw.columns:
        return by_day
    for ts, px in raw["Close"].dropna().items():
        d = ts.date().isoformat()
        by_day.setdefault(d, {})[t] = float(px)
    return by_day


def backfill_missing_mtm_rows(
    *,
    trade_date: str,
    portfolio_state: Any,
    source: str = "mtm_backfill",
) -> Dict[str, Any]:
    """
    Backfill missing weekday rows between latest history row and ``trade_date``.

    Rows are mark-to-market only (no trades): holdings/shares stay fixed, cash is
    constant, equity changes with close prices.
    """
    latest = get_latest_row()
    if latest is None:
        return {"backfilled_days": 0, "rows": [], "warnings": ["No existing history row to backfill from."]}

    latest_date = _parse_date(str(latest["as_of_date"]))
    end_date = _parse_date(trade_date)
    if end_date <= latest_date:
        return {
            "backfilled_days": 0,
            "rows": [],
            "backfill_start": latest_date.isoformat(),
            "backfill_end": latest_date.isoformat(),
            "warnings": [],
        }

    days = _iter_weekdays(latest_date, end_date - timedelta(days=1))
    if not days:
        return {
            "backfilled_days": 0,
            "rows": [],
            "backfill_start": latest_date.isoformat(),
            "backfill_end": latest_date.isoformat(),
            "warnings": [],
        }

    shares = {str(t): float(sh) for t, sh in dict(getattr(portfolio_state, "shares", {})).items() if abs(float(sh)) > 1e-12}
    cash = float(getattr(portfolio_state, "cash", 0.0))

    warnings: List[str] = []
    rows: List[Dict[str, Any]] = []
    prev_eq = float(latest["equity_after"])

    if not shares:
        for d in days:
            row = upsert_paper_daily_row(
                as_of_date=d.isoformat(),
                equity_before=prev_eq,
                equity_after=cash,
                cash_after=cash,
                n_positions=0,
                gross_long=0.0,
                gross_short=0.0,
                trades_count=0,
                source=source,
                holdings_weights={},
            )
            prev_eq = float(row["equity_after"])
            rows.append(row)
        return {
            "backfilled_days": len(rows),
            "rows": rows,
            "backfill_start": days[0].isoformat(),
            "backfill_end": days[-1].isoformat(),
            "warnings": warnings,
        }

    tickers = sorted(shares.keys())
    fetch_start = latest_date.isoformat()
    fetch_end = (end_date + timedelta(days=1)).isoformat()
    raw = yf.download(
        tickers=tickers,
        start=fetch_start,
        end=fetch_end,
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    close_panel = _extract_close_panel(raw, tickers)

    last_valid: Dict[str, float] = {}
    latest_day = latest_date.isoformat()
    if latest_day in close_panel:
        for t in tickers:
            px = close_panel[latest_day].get(t)
            if px is not None and px > 0:
                last_valid[t] = float(px)

    for d in days:
        ds = d.isoformat()
        day_prices = close_panel.get(ds, {})
        priced: Dict[str, float] = {}
        missing: List[str] = []
        for t in tickers:
            px = day_prices.get(t)
            if px is not None and px > 0:
                last_valid[t] = float(px)
                priced[t] = float(px)
                continue
            if t in last_valid and last_valid[t] > 0:
                priced[t] = float(last_valid[t])
                continue
            missing.append(t)

        if missing:
            warnings.append(f"{ds}: skipped row; missing prices for {', '.join(missing[:8])}")
            continue

        exposures = {t: shares[t] * priced[t] for t in tickers}
        equity = cash + sum(exposures.values())
        if abs(equity) <= 1e-12:
            warnings.append(f"{ds}: skipped row; non-positive equity {equity:.6f}")
            continue

        holdings_weights = {t: exposures[t] / equity for t in tickers}
        gross_long = sum(w for w in holdings_weights.values() if w > 0)
        gross_short = -sum(w for w in holdings_weights.values() if w < 0)

        row = upsert_paper_daily_row(
            as_of_date=ds,
            equity_before=prev_eq,
            equity_after=equity,
            cash_after=cash,
            n_positions=sum(1 for sh in shares.values() if abs(sh) > 1e-12),
            gross_long=float(gross_long),
            gross_short=float(gross_short),
            trades_count=0,
            source=source,
            holdings_weights=holdings_weights,
        )
        prev_eq = float(row["equity_after"])
        rows.append(row)

    return {
        "backfilled_days": len(rows),
        "rows": rows,
        "backfill_start": days[0].isoformat(),
        "backfill_end": days[-1].isoformat(),
        "warnings": warnings,
    }
