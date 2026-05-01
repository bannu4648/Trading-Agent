from __future__ import annotations

import argparse
import glob
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from technical_agent.agent import TechnicalAnalystAgent
from technical_agent.config import config_from_env
from portfolio_history import append_paper_daily_row
from portfolio_history.store import get_latest_row
from portfolio_history.backfill import backfill_missing_mtm_rows
from paper_simulator.simulator import ExecutionParams, PortfolioState, compute_daily_metrics, rebalance_to_target_weights


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily-paper")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse_date(s: str) -> str:
    datetime.strptime(s, "%Y-%m-%d")
    return s


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else _PROJECT_ROOT / p


def _load_state(path: Path, initial_cash: float) -> PortfolioState:
    if not path.exists():
        return PortfolioState(cash=float(initial_cash), shares={})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PortfolioState(cash=float(payload.get("cash", initial_cash)), shares=dict(payload.get("shares", {})))


def _save_state(path: Path, state: PortfolioState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cash": state.cash, "shares": state.shares}, indent=2), encoding="utf-8")


def _migrate_or_seed_state_file(state_path: Path) -> None:
    """
    Keep continuity when switching to a dedicated S&P state file.

    If new file is missing and legacy `paper_state.json` exists, copy it once.
    """
    if state_path.exists():
        return
    legacy = _PROJECT_ROOT / "results" / "paper_state.json"
    if legacy.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")


def _extract_close_prices(tech_output: dict[str, Any], tickers: list[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    by_ticker = tech_output.get("tickers", {}) if isinstance(tech_output, dict) else {}
    for t in tickers:
        try:
            ind = by_ticker.get(t, {}).get("indicators", {})
            values = ind.get("values", ind)
            close = values.get("close") or values.get("Close")
            if close is None:
                continue
            prices[t] = float(close)
        except Exception:
            continue
    return prices


def _latest_sp500_result_path() -> Path | None:
    pattern = str(_PROJECT_ROOT / "results" / "sp500_screened_*.json")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        return None
    return Path(candidates[-1])


def _load_latest_sp500_targets() -> tuple[Path, dict[str, float], list[str]]:
    latest = _latest_sp500_result_path()
    if latest is None:
        raise RuntimeError("No sp500_screened_*.json file found in results/")
    payload = json.loads(latest.read_text(encoding="utf-8"))
    targets_raw = payload.get("target_weights", {}) if isinstance(payload, dict) else {}
    targets: dict[str, float] = {}
    for ticker, weight in dict(targets_raw).items():
        try:
            w = float(weight)
        except Exception:
            continue
        if abs(w) > 1e-12:
            targets[str(ticker).upper()] = w
    if not targets:
        raise RuntimeError(f"No non-zero target_weights found in {latest.name}")
    return latest, targets, sorted(targets.keys())


def _seed_state_from_targets(
    *,
    state: PortfolioState,
    targets: dict[str, float],
    prices: dict[str, float],
) -> dict[str, Any]:
    """One-time bootstrap when state has no holdings yet."""
    return rebalance_to_target_weights(
        state,
        target_weights=targets,
        prices=prices,
        exec_params=ExecutionParams(),
    )


def run_daily_paper_trade_job(
    *,
    trade_date: str,
    k_long: int = 25,
    k_short: int = 25,
    gross_long: float = 1.0,
    gross_short: float = 0.5,
    max_single_long: float = 0.05,
    max_single_short: float = 0.03,
    lookback_days: int = 365,
    initial_cash: float = 100_000.0,
    state_file: str = "results/paper_state_sp500.json",
    no_llm: bool = False,
    live_sentiment: bool = False,
    live_fundamentals: bool = False,
    live_synthesis: bool = False,
    candidate_pool_mult: int = 3,
    limit_universe: int = 0,
    history_source: str = "daily_cli",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Full S&P 500 screened daily paper rebalance: technicals → screen → optional live enrichment
    → adapter → allocator → rebalance → snapshot + SQLite history row.

    ``state_file`` is resolved under the project root if relative.
    """
    _parse_date(trade_date)
    source_tag = (history_source or "pnl_update").strip() or "pnl_update"

    def _emit(step: str, label: str) -> None:
        if progress_callback:
            try:
                progress_callback({"pipeline_step": step, "pipeline_step_label": label})
            except Exception as exc:
                logger.warning("progress_callback failed: %s", exc)

    end = datetime.strptime(trade_date, "%Y-%m-%d")
    start = (end - timedelta(days=max(int(lookback_days), 30))).strftime("%Y-%m-%d")
    latest_portfolio_path, latest_targets, latest_tickers = _load_latest_sp500_targets()
    if limit_universe and limit_universe > 0:
        logger.warning("[daily] limit_universe is ignored for daily PnL updates to preserve portfolio continuity.")

    _emit("portfolio", f"Loaded latest S&P500 portfolio ({len(latest_tickers)} names)…")
    logger.info(
        "[daily] Source portfolio=%s tickers=%s start=%s end=%s",
        latest_portfolio_path.name,
        len(latest_tickers),
        start,
        trade_date,
    )
    _emit("technical", f"Refreshing closes for current holdings ({len(latest_tickers)} names)…")
    tech_config = config_from_env()
    tech_config.enable_llm_summary = False
    tech = TechnicalAnalystAgent(config=tech_config).run(
        latest_tickers, start_date=start, end_date=trade_date, interval="1d"
    )

    prices = _extract_close_prices(tech, latest_tickers)
    tradable = [t for t in latest_tickers if t in prices and prices[t] > 0]

    state_path = _resolve_path(state_file)
    _migrate_or_seed_state_file(state_path)
    state = _load_state(state_path, initial_cash=initial_cash)
    had_positions = any(abs(float(sh)) > 1e-12 for sh in state.shares.values())
    latest_set = {t for t, w in latest_targets.items() if abs(float(w)) > 1e-12}

    latest_hist = get_latest_row()
    if not had_positions and latest_hist is not None:
        # Do not silently reset to 100k when history already exists.
        raise RuntimeError(
            "State file has no holdings while paper history already exists. "
            "Provide the previous state file or restore continuity before running."
        )

    if not had_positions:
        _emit("seed", "Seeding paper state from latest S&P500 target weights…")
        seed_targets = {t: w for t, w in latest_targets.items() if t in prices and prices[t] > 0}
        if not seed_targets:
            raise RuntimeError("No priced tickers available from latest S&P500 targets for state seeding")
        _seed_state_from_targets(state=state, targets=seed_targets, prices=prices)
    else:
        held_now = {t for t, sh in state.shares.items() if abs(float(sh)) > 1e-12}
        if held_now != latest_set:
            _emit("realign", "Holdings drift detected — realigning to latest S&P500 portfolio…")
            seed_targets = {t: w for t, w in latest_targets.items() if t in prices and prices[t] > 0}
            if not seed_targets:
                raise RuntimeError("Cannot realign: no priced tickers from latest S&P500 targets")
            _seed_state_from_targets(state=state, targets=seed_targets, prices=prices)

    held_tickers = sorted([t for t, sh in state.shares.items() if abs(float(sh)) > 1e-12])
    if not held_tickers:
        raise RuntimeError("Paper state has no holdings after initialization")
    valuation_prices = {t: prices[t] for t in held_tickers if t in prices and prices[t] > 0}
    missing_held = sorted(set(held_tickers) - set(valuation_prices))
    if missing_held:
        raise RuntimeError(f"Missing close prices for held tickers: {', '.join(missing_held[:12])}")

    _emit("backfill", "Backfilling missing paper history days…")
    backfill_info = backfill_missing_mtm_rows(
        trade_date=trade_date,
        portfolio_state=state,
        source=source_tag,
    )

    _emit("pnl", "Updating mark-to-market PnL (no rebalance)…")
    before = compute_daily_metrics(state, valuation_prices)
    after = compute_daily_metrics(state, valuation_prices)

    _save_state(state_path, state)
    snapshot_path = _PROJECT_ROOT / "results" / f"paper_snapshot_{trade_date}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "date": trade_date,
                "before": before,
                "after": after,
                "rebalance": {"trades": [], "note": "pnl_update_no_rebalance"},
                "targets": latest_targets,
                "portfolio_source_file": latest_portfolio_path.name,
                "holdings": held_tickers,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("[daily] Saved state → %s", state_path)
    logger.info("[daily] Saved snapshot → %s", snapshot_path)

    hist: Optional[Dict[str, Any]] = None
    hist_err: Optional[str] = None
    try:
        hist = append_paper_daily_row(
            as_of_date=trade_date,
            equity_before=float(before["equity"]),
            equity_after=float(after["equity"]),
            cash_after=float(after["cash"]),
            n_positions=int(after["n_positions"]),
            gross_long=float(after["gross_long"]),
            gross_short=float(after["gross_short"]),
            trades_count=0,
            source=source_tag,
            holdings_weights=dict(state.weights(valuation_prices)),
        )
        logger.info(
            "[daily] History row → %s daily_return_pct=%s",
            hist.get("as_of_date"),
            hist.get("daily_return_pct"),
        )
    except Exception as exc:
        hist_err = str(exc)
        logger.warning("[daily] Failed to append paper history: %s", exc)

    _emit("done", "Daily paper run complete")
    return {
        "skipped": False,
        "trade_date": trade_date,
        "metadata": {
            "state_path": str(state_path),
            "snapshot_path": str(snapshot_path),
            "tradable_count": len(tradable),
            "candidate_count": len(held_tickers),
            "portfolio_source_file": latest_portfolio_path.name,
            "source_tag": source_tag,
            "backfilled_days": int(backfill_info.get("backfilled_days", 0)),
            "backfill_start": backfill_info.get("backfill_start"),
            "backfill_end": backfill_info.get("backfill_end"),
            "backfill_warnings": backfill_info.get("warnings", []),
        },
        "before": before,
        "after": after,
        "rebalance": {"trades": [], "note": "pnl_update_no_rebalance"},
        "targets": latest_targets,
        "candidates": held_tickers,
        "portfolio_source_file": latest_portfolio_path.name,
        "source_tag": source_tag,
        "backfill": backfill_info,
        "history_record": hist,
        "history_error": hist_err,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily long/short paper trading run (simulated).")
    parser.add_argument("--date", required=True, type=_parse_date, help="Trade date YYYY-MM-DD (uses close prices).")
    parser.add_argument("--k-long", type=int, default=25)
    parser.add_argument("--k-short", type=int, default=25)
    parser.add_argument("--gross-long", type=float, default=1.0)
    parser.add_argument("--gross-short", type=float, default=0.5)
    parser.add_argument("--max-single-long", type=float, default=0.05)
    parser.add_argument("--max-single-short", type=float, default=0.03)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument(
        "--state-file",
        default=str(_PROJECT_ROOT / "results" / "paper_state_sp500.json"),
        help="Portfolio state JSON (relative paths are under project root).",
    )
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM interpretation (force formula decisions).")
    parser.add_argument("--live-sentiment", action="store_true", help="Fetch latest sentiment/news for candidates.")
    parser.add_argument("--live-fundamentals", action="store_true", help="Fetch latest fundamentals for candidates.")
    parser.add_argument("--live-synthesis", action="store_true", help="Run summarizer synthesis for candidates (LLM).")
    parser.add_argument("--candidate-pool-mult", type=int, default=3)
    parser.add_argument("--limit-universe", type=int, default=0, help="Debug: only use first N tickers.")
    args = parser.parse_args()

    run_daily_paper_trade_job(
        trade_date=args.date,
        k_long=args.k_long,
        k_short=args.k_short,
        gross_long=args.gross_long,
        gross_short=args.gross_short,
        max_single_long=args.max_single_long,
        max_single_short=args.max_single_short,
        lookback_days=args.lookback_days,
        initial_cash=args.initial_cash,
        state_file=args.state_file,
        no_llm=args.no_llm,
        live_sentiment=args.live_sentiment,
        live_fundamentals=args.live_fundamentals,
        live_synthesis=args.live_synthesis,
        candidate_pool_mult=args.candidate_pool_mult,
        limit_universe=args.limit_universe,
        history_source="pnl_update",
    )


if __name__ == "__main__":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    main()
