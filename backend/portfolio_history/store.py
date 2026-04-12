"""
SQLite table ``paper_daily`` — one row per as-of date for simulated paper portfolio.

Used by ``run_daily_paper_trade.py`` and ``paper_execution.run_paper_rebalance_optional``.
Override path with env ``PAPER_HISTORY_DB`` (absolute or relative path).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_FILE = "paper_daily_history.sqlite"


def _results_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "results"


def get_database_path() -> Path:
    env = os.environ.get("PAPER_HISTORY_DB", "").strip()
    if env:
        return Path(env).expanduser()
    return _results_dir() / _DEFAULT_FILE


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_daily (
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
    cols = {row[1] for row in conn.execute("PRAGMA table_info(paper_daily)").fetchall()}
    if "holdings_weights_json" not in cols:
        conn.execute("ALTER TABLE paper_daily ADD COLUMN holdings_weights_json TEXT")
        conn.commit()


def _prev_equity_after(conn: sqlite3.Connection, as_of_date: str) -> Optional[float]:
    row = conn.execute(
        """
        SELECT equity_after FROM paper_daily
        WHERE as_of_date < ?
        ORDER BY as_of_date DESC LIMIT 1
        """,
        (as_of_date,),
    ).fetchone()
    return float(row[0]) if row else None


def append_paper_daily_row(
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
    holdings_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Insert or replace row for ``as_of_date`` (YYYY-MM-DD). Computes ``daily_return_pct`` vs prior row."""
    path = get_database_path()
    conn = _connect(path)
    try:
        init_schema(conn)
        prev_eq = _prev_equity_after(conn, as_of_date)
        daily_ret: Optional[float] = None
        if prev_eq is not None and prev_eq > 1e-12:
            daily_ret = (float(equity_after) / prev_eq) - 1.0

        created = datetime.now(timezone.utc).isoformat()
        hw_json: Optional[str] = None
        if holdings_weights is not None:
            hw_json = json.dumps(
                {k: round(float(v), 6) for k, v in holdings_weights.items()},
                sort_keys=True,
            )

        conn.execute(
            """
            INSERT OR REPLACE INTO paper_daily (
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
                created,
                hw_json,
            ),
        )
        conn.commit()
        return {
            "as_of_date": as_of_date,
            "equity_after": float(equity_after),
            "daily_return_pct": daily_ret,
        }
    finally:
        conn.close()


def _row_dict_from_tuple(r: tuple[Any, ...]) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "as_of_date": r[0],
        "equity_before": r[1],
        "equity_after": r[2],
        "daily_return_pct": r[3],
        "cash_after": r[4],
        "n_positions": r[5],
        "gross_long": r[6],
        "gross_short": r[7],
        "trades_count": r[8],
        "source": r[9],
        "created_at": r[10],
    }
    hwj = r[11] if len(r) > 11 else None
    if hwj:
        try:
            d["holdings_weights"] = json.loads(str(hwj))
        except (json.JSONDecodeError, TypeError):
            d["holdings_weights"] = None
    else:
        d["holdings_weights"] = None
    return d


_SELECT_ROW = """
    SELECT as_of_date, equity_before, equity_after, daily_return_pct,
           cash_after, n_positions, gross_long, gross_short,
           trades_count, source, created_at, holdings_weights_json
    FROM paper_daily
"""


def get_row_for_date(as_of_date: str) -> Optional[Dict[str, Any]]:
    """Return the ``paper_daily`` row for ``as_of_date`` (YYYY-MM-DD), or ``None``."""
    path = get_database_path()
    if not path.exists():
        return None
    conn = _connect(path)
    try:
        init_schema(conn)
        row = conn.execute(
            _SELECT_ROW + " WHERE as_of_date = ?",
            (as_of_date,),
        ).fetchone()
        return _row_dict_from_tuple(row) if row else None
    finally:
        conn.close()


def list_paper_daily_rows(*, limit: int = 2000) -> List[Dict[str, Any]]:
    """Rows in chronological order (oldest first), with ``cumulative_return_pct`` vs first row in series."""
    path = get_database_path()
    if not path.exists():
        return []

    conn = _connect(path)
    try:
        init_schema(conn)
        cap = max(1, min(int(limit), 50_000))
        raw = conn.execute(
            _SELECT_ROW + " ORDER BY as_of_date DESC LIMIT ?",
            (cap,),
        ).fetchall()
    finally:
        conn.close()

    rows: List[Dict[str, Any]] = [_row_dict_from_tuple(r) for r in reversed(raw)]

    if not rows:
        return []

    base = float(rows[0]["equity_after"])
    prev_eq: float | None = None
    for d in rows:
        eq = float(d["equity_after"])
        d["cumulative_return_pct"] = (eq / base - 1.0) if base > 1e-12 else None
        if prev_eq is not None:
            d["day_pnl_dollars"] = round(eq - prev_eq, 2)
        else:
            d["day_pnl_dollars"] = None
        prev_eq = eq

    return rows
