from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from paper_simulator.simulator import ExecutionParams, PortfolioState, compute_daily_metrics, rebalance_to_target_weights

_STARTING_EQUITY = 100_000.0


def _results_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "results"


def get_database_path() -> Path:
    return _results_dir() / "top20_daily_history.sqlite"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS top20_daily (
            as_of_date TEXT PRIMARY KEY,
            equity_before REAL NOT NULL,
            equity_after REAL NOT NULL,
            daily_return_pct REAL,
            cash_after REAL NOT NULL,
            n_positions INTEGER NOT NULL,
            gross_long REAL,
            gross_short REAL,
            trades_count INTEGER NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            holdings_weights_json TEXT
        )
        """
    )
    conn.commit()
    conn.execute(
        "UPDATE top20_daily SET gross_short = ABS(gross_short) "
        "WHERE gross_short IS NOT NULL AND gross_short < 0"
    )
    conn.commit()


def _upsert_row(
    conn: sqlite3.Connection,
    *,
    as_of_date: str,
    equity_before: float,
    equity_after: float,
    cash_after: float,
    n_positions: int,
    gross_long: float,
    gross_short: float,
    trades_count: int,
    source: str,
    holdings_weights: Dict[str, float],
) -> None:
    prev = conn.execute(
        "SELECT equity_after FROM top20_daily WHERE as_of_date < ? ORDER BY as_of_date DESC LIMIT 1",
        (as_of_date,),
    ).fetchone()
    daily_ret: Optional[float] = None
    if prev and float(prev[0]) > 1e-12:
        daily_ret = (float(equity_after) / float(prev[0])) - 1.0
    conn.execute(
        """
        INSERT OR REPLACE INTO top20_daily (
            as_of_date, equity_before, equity_after, daily_return_pct,
            cash_after, n_positions, gross_long, gross_short,
            trades_count, source, created_at, holdings_weights_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            as_of_date,
            float(equity_before),
            float(equity_after),
            daily_ret,
            float(cash_after),
            int(n_positions),
            float(gross_long),
            float(gross_short),
            int(trades_count),
            source,
            datetime.utcnow().isoformat(),
            json.dumps({k: round(float(v), 6) for k, v in holdings_weights.items()}, sort_keys=True),
        ),
    )


def _parse_top20_files() -> List[Dict[str, Any]]:
    files = sorted(_results_dir().glob("top20_longshort_*.json"))
    runs: List[Dict[str, Any]] = []
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = data.get("metadata", {}) if isinstance(data, dict) else {}
        date_s = md.get("as_of_end_date")
        tw = data.get("target_weights", {}) if isinstance(data, dict) else {}
        if not date_s or not isinstance(tw, dict):
            continue
        targets = {str(t).upper(): float(w) for t, w in tw.items() if abs(float(w)) > 1e-12}
        if not targets:
            continue
        runs.append({"as_of_date": str(date_s), "targets": targets, "file": p.name})
    runs.sort(key=lambda x: x["as_of_date"])
    return runs


def _iter_weekdays(start_inclusive: date, end_inclusive: date) -> List[date]:
    out: List[date] = []
    d = start_inclusive
    while d <= end_inclusive:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _trading_days_after_through(last_row_date: date, end_inclusive: date) -> List[date]:
    """Weekdays strictly after ``last_row_date`` up to and including ``end_inclusive``."""
    out: List[date] = []
    d = last_row_date + timedelta(days=1)
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
        for t in tickers:
            try:
                close_series = raw[t]["Close"]
            except Exception:
                continue
            for ts, px in close_series.dropna().items():
                by_day.setdefault(ts.date().isoformat(), {})[t] = float(px)
        return by_day
    if len(tickers) == 1 and "Close" in raw.columns:
        t = tickers[0]
        for ts, px in raw["Close"].dropna().items():
            by_day.setdefault(ts.date().isoformat(), {})[t] = float(px)
    return by_day


def rebuild_top20_history() -> Dict[str, Any]:
    runs = _parse_top20_files()
    path = get_database_path()
    conn = _connect(path)
    try:
        _init_schema(conn)
        conn.execute("DELETE FROM top20_daily")
        conn.commit()
        if not runs:
            return {"rebuilt_rows": 0, "database": str(path.resolve())}

        run_map = {r["as_of_date"]: r["targets"] for r in runs}
        all_tickers = sorted({t for r in runs for t in r["targets"].keys()})
        first_run = datetime.strptime(runs[0]["as_of_date"], "%Y-%m-%d").date()
        last_run = datetime.strptime(runs[-1]["as_of_date"], "%Y-%m-%d").date()
        min_date = first_run - timedelta(days=7)
        max_date = last_run + timedelta(days=2)
        raw = yf.download(
            tickers=all_tickers,
            start=min_date.isoformat(),
            end=max_date.isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        panel = _extract_close_panel(raw, all_tickers)
        last_px: Dict[str, float] = {}
        state = PortfolioState(cash=float(_STARTING_EQUITY), shares={})
        inserted = 0

        for d in _iter_weekdays(first_run, last_run):
            ds = d.isoformat()
            day_prices = panel.get(ds, {})
            prices: Dict[str, float] = {}
            for t in all_tickers:
                px = day_prices.get(t)
                if px is not None and px > 0:
                    last_px[t] = float(px)
                    prices[t] = float(px)
                elif t in last_px and last_px[t] > 0:
                    prices[t] = float(last_px[t])
            targets = run_map.get(ds)
            if targets is not None and any(t not in prices for t in targets.keys()):
                continue
            held = [t for t, sh in state.shares.items() if abs(float(sh)) > 1e-12]
            if targets is None and held and any(t not in prices for t in held):
                continue

            before = compute_daily_metrics(state, prices) if (targets is not None or held) else None
            trades_count = 0
            source = "pnl_update"
            if targets is not None:
                trades = rebalance_to_target_weights(
                    state,
                    target_weights=targets,
                    prices=prices,
                    exec_params=ExecutionParams(),
                )
                trades_count = len(trades.get("trades") or [])
                source = "live_rebalance"
            if before is None:
                continue
            after = compute_daily_metrics(state, prices)
            _upsert_row(
                conn,
                as_of_date=ds,
                equity_before=float(before["equity"]),
                equity_after=float(after["equity"]),
                cash_after=float(after["cash"]),
                n_positions=int(after["n_positions"]),
                gross_long=float(after["gross_long"]),
                gross_short=abs(float(after["gross_short"])),
                trades_count=trades_count,
                source=source,
                holdings_weights=dict(state.weights(prices)),
            )
            inserted += 1
        conn.commit()
        return {"rebuilt_rows": inserted, "database": str(path.resolve())}
    finally:
        conn.close()


def list_top20_rows(limit: int = 2000) -> List[Dict[str, Any]]:
    path = get_database_path()
    if not path.exists():
        return []
    conn = _connect(path)
    try:
        _init_schema(conn)
        cap = max(1, min(int(limit), 50_000))
        rows = conn.execute(
            """
            SELECT as_of_date, equity_before, equity_after, daily_return_pct,
                   cash_after, n_positions, gross_long, gross_short,
                   trades_count, source, created_at, holdings_weights_json
            FROM top20_daily
            ORDER BY as_of_date DESC
            LIMIT ?
            """,
            (cap,),
        ).fetchall()
    finally:
        conn.close()

    out: List[Dict[str, Any]] = []
    for r in reversed(rows):
        hw = None
        if r[11]:
            try:
                hw = json.loads(str(r[11]))
            except Exception:
                hw = None
        out.append(
            {
                "as_of_date": r[0],
                "equity_before": r[1],
                "equity_after": r[2],
                "daily_return_pct": r[3],
                "cash_after": r[4],
                "n_positions": r[5],
                "gross_long": r[6],
                "gross_short": abs(float(r[7])) if r[7] is not None else None,
                "trades_count": r[8],
                "source": r[9],
                "created_at": r[10],
                "holdings_weights": hw,
            }
        )

    prev_eq: Optional[float] = None
    for row in out:
        eq = float(row["equity_after"])
        row["cumulative_return_pct"] = (eq / _STARTING_EQUITY - 1.0) if _STARTING_EQUITY > 1e-12 else None
        row["day_pnl_dollars"] = None if prev_eq is None else round(eq - prev_eq, 2)
        prev_eq = eq
    return out


def ensure_top20_history_exists() -> Dict[str, Any]:
    path = get_database_path()
    if not path.exists():
        return rebuild_top20_history()
    conn = _connect(path)
    try:
        _init_schema(conn)
        row = conn.execute("SELECT COUNT(*) FROM top20_daily").fetchone()
        count = int(row[0]) if row else 0
    finally:
        conn.close()
    if count == 0:
        return rebuild_top20_history()
    return {"rebuilt_rows": 0, "database": str(path.resolve())}


def _append_top20_mtm_for_date(trade_date: str) -> Dict[str, Any]:
    """
    One sequential MTM step: previous row equity + weights repriced to ``trade_date`` closes.
    Caller must ensure ``trade_date`` is strictly after the latest stored row date.
    """
    path = get_database_path()
    conn = _connect(path)
    try:
        _init_schema(conn)
        latest = conn.execute(
            """
            SELECT as_of_date, equity_after, cash_after, holdings_weights_json
            FROM top20_daily
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return {"updated": False, "reason": "no_top20_history"}
        last_date = str(latest[0])
        if trade_date <= last_date:
            return {"updated": False, "reason": "trade_date_not_after_latest", "latest_date": last_date}
        eq_prev = float(latest[1])
        cash_prev = float(latest[2])
        hw = json.loads(str(latest[3] or "{}"))
    finally:
        conn.close()

    tickers = sorted([t for t, w in hw.items() if abs(float(w)) > 1e-12])
    if not tickers:
        return {"updated": False, "reason": "no_holdings"}

    fetch_start = (datetime.strptime(last_date, "%Y-%m-%d").date() - timedelta(days=7)).isoformat()
    fetch_end = (datetime.strptime(trade_date, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
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
    panel = _extract_close_panel(raw, tickers)
    days_sorted = sorted(panel.keys())
    last_d = datetime.strptime(last_date, "%Y-%m-%d").date()
    trade_d = datetime.strptime(trade_date, "%Y-%m-%d").date()
    p_prev: Dict[str, float] = {}
    p_now: Dict[str, float] = {}
    for t in tickers:
        prev_px: Optional[float] = None
        now_px: Optional[float] = None
        for ds in days_sorted:
            d0 = datetime.strptime(ds, "%Y-%m-%d").date()
            px = panel.get(ds, {}).get(t)
            if px is None or px <= 0:
                continue
            if d0 <= last_d:
                prev_px = float(px)
            if d0 <= trade_d:
                now_px = float(px)
        if prev_px is not None:
            p_prev[t] = prev_px
        if now_px is not None:
            p_now[t] = now_px

    missing: List[str] = []
    for t in tickers:
        prev_px = p_prev.get(t)
        now_px = p_now.get(t)
        if prev_px is None and now_px is None:
            p_prev[t] = 1.0
            p_now[t] = 1.0
            missing.append(t)
            continue
        if prev_px is None and now_px is not None:
            p_prev[t] = float(now_px)
            missing.append(t)
            continue
        if now_px is None and prev_px is not None:
            p_now[t] = float(prev_px)
            missing.append(t)

    shares = {t: (float(hw[t]) * eq_prev) / float(p_prev[t]) for t in tickers}
    state = PortfolioState(cash=cash_prev, shares=shares)
    before = compute_daily_metrics(state, p_now)
    after = compute_daily_metrics(state, p_now)

    conn2 = _connect(path)
    try:
        _init_schema(conn2)
        _upsert_row(
            conn2,
            as_of_date=trade_date,
            equity_before=float(before["equity"]),
            equity_after=float(after["equity"]),
            cash_after=float(after["cash"]),
            n_positions=int(after["n_positions"]),
            gross_long=float(after["gross_long"]),
            gross_short=abs(float(after["gross_short"])),
            trades_count=0,
            source="pnl_update",
            holdings_weights=dict(state.weights(p_now)),
        )
        conn2.commit()
    finally:
        conn2.close()

    return {
        "updated": True,
        "trade_date": trade_date,
        "latest_date": last_date,
        "missing_prices_fallback": sorted(set(missing)),
    }


def run_top20_pnl_update(trade_date: str) -> Dict[str, Any]:
    """
    Replay from saved Top‑20 JSONs, then sequentially mark-to-market for each missing
    weekday until ``trade_date`` (aligned with SQLite row dates).
    """
    rebuild_top20_history()
    end_d = datetime.strptime(trade_date, "%Y-%m-%d").date()
    day_results: List[Dict[str, Any]] = []
    processed_dates: List[str] = []

    while True:
        path = get_database_path()
        conn = _connect(path)
        try:
            _init_schema(conn)
            latest = conn.execute("SELECT MAX(as_of_date) FROM top20_daily").fetchone()
        finally:
            conn.close()

        if latest is None or latest[0] is None:
            return {
                "updated": False,
                "trade_date": trade_date,
                "reason": "no_top20_history",
                "days_processed": 0,
                "processed_dates": [],
                "results": day_results,
            }

        last_d = datetime.strptime(str(latest[0]), "%Y-%m-%d").date()
        gap = _trading_days_after_through(last_d, end_d)
        if not gap:
            return {
                "updated": len(processed_dates) > 0,
                "trade_date": trade_date,
                "reason": "caught_up" if processed_dates else "already_current",
                "latest_date": str(latest[0]),
                "days_processed": len(processed_dates),
                "processed_dates": processed_dates,
                "results": day_results,
            }

        ds = gap[0].isoformat()
        one = _append_top20_mtm_for_date(ds)
        day_results.append(one)
        if not one.get("updated"):
            return {
                "updated": len(processed_dates) > 0,
                "trade_date": trade_date,
                "reason": one.get("reason", "append_failed"),
                "days_processed": len(processed_dates),
                "processed_dates": processed_dates,
                "results": day_results,
                "last_error_detail": one,
            }
        processed_dates.append(ds)
