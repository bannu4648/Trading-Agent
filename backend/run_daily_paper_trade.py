from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from technical_agent.agent import TechnicalAnalystAgent
from technical_agent.config import config_from_env
from trader_agent.adapter import build_research_output

from sentiment_agent.agents.orchestrator_agent import OrchestratorAgent
from fundamentals_agent.tools import fetch_fundamentals_data
from summarizer_agent import SummarizerAgent

from portfolio_history import append_paper_daily_row
from portfolio_history.backfill import backfill_missing_mtm_rows
from risk_portfolio_agent import RiskPortfolioAgent, RiskPortfolioConfig
from paper_simulator.simulator import ExecutionParams, PortfolioState, compute_daily_metrics, rebalance_to_target_weights
from universe.sp500 import get_sp500_tickers
from universe.screen import select_candidates_by_expected_return


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


def _safe_sentiment(ticker: str) -> dict[str, Any]:
    try:
        return OrchestratorAgent().run(ticker)
    except Exception as exc:
        logger.warning("[daily] Sentiment failed for %s: %s", ticker, exc)
        return {}


def _safe_fundamentals(ticker: str) -> dict[str, Any]:
    try:
        return fetch_fundamentals_data(ticker, try_alpha_vantage=False)
    except Exception as exc:
        logger.warning("[daily] Fundamentals failed for %s: %s", ticker, exc)
        return {}


def _safe_synthesis(ticker: str, combined: dict[str, Any]) -> str:
    try:
        return SummarizerAgent().run(ticker, combined)
    except Exception as exc:
        logger.warning("[daily] Synthesis failed for %s: %s", ticker, exc)
        return ""


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
    state_file: str = "results/paper_state.json",
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

    def _emit(step: str, label: str) -> None:
        if progress_callback:
            try:
                progress_callback({"pipeline_step": step, "pipeline_step_label": label})
            except Exception as exc:
                logger.warning("progress_callback failed: %s", exc)

    tickers = get_sp500_tickers()
    if limit_universe and limit_universe > 0:
        tickers = tickers[: int(limit_universe)]

    end = datetime.strptime(trade_date, "%Y-%m-%d")
    start = (end - timedelta(days=int(lookback_days))).strftime("%Y-%m-%d")

    _emit("technical", f"Technical analysis ({len(tickers)} names)…")
    logger.info("[daily] Universe=%s start=%s end=%s", len(tickers), start, trade_date)
    tech_config = config_from_env()
    if no_llm:
        tech_config.enable_llm_summary = False
    tech = TechnicalAnalystAgent(config=tech_config).run(
        tickers, start_date=start, end_date=trade_date, interval="1d"
    )

    prices = _extract_close_prices(tech, tickers)
    tradable = [t for t in tickers if t in prices and prices[t] > 0]
    logger.info("[daily] Tradable=%s", len(tradable))
    _emit("screen", f"Screening — {len(tickers)} names ranked ({len(tradable)} with usable close)")

    combined: Dict[str, Any] = {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers": tickers},
        "results": {},
    }
    tech_by = tech.get("tickers", {}) if isinstance(tech, dict) else {}
    for t in tickers:
        combined["results"][t] = {
            "technical": tech_by.get(t, {}),
            "sentiment": {},
            "fundamentals": {},
            "synthesis": "",
        }

    prelim = build_research_output(combined_results=combined, current_weights=None, use_llm=False)
    candidate_set = select_candidates_by_expected_return(
        prelim.recommendations,
        k_long=k_long,
        k_short=k_short,
        pool_mult=candidate_pool_mult,
    )
    combined["results"] = {t: combined["results"][t] for t in candidate_set}
    combined["metadata"]["tickers"] = list(candidate_set)

    if live_sentiment or live_fundamentals or live_synthesis:
        logger.info(
            "[daily] Live enrichment: candidates=%s sentiment=%s fundamentals=%s synthesis=%s",
            len(candidate_set),
            live_sentiment,
            live_fundamentals,
            live_synthesis,
        )
        _emit("enrich", f"Live enrichment ({len(candidate_set)} candidates)…")
    for t in candidate_set:
        if live_sentiment:
            combined["results"][t]["sentiment"] = _safe_sentiment(t)
        if live_fundamentals:
            combined["results"][t]["fundamentals"] = _safe_fundamentals(t)
        if live_synthesis:
            combined["results"][t]["synthesis"] = _safe_synthesis(t, combined)

    _emit("adapter", "Building recommendations & targets…")
    recs = build_research_output(combined_results=combined, current_weights=None, use_llm=not no_llm)
    targets = RiskPortfolioAgent(
        RiskPortfolioConfig(
            k_long=k_long,
            k_short=k_short,
            gross_long=gross_long,
            gross_short=gross_short,
            max_single_long=max_single_long,
            max_single_short=max_single_short,
        )
    ).build_target_weights(recs.recommendations)

    state_path = _resolve_path(state_file)
    state = _load_state(state_path, initial_cash=initial_cash)

    _emit("backfill", "Backfilling missing paper history days…")
    backfill_info = backfill_missing_mtm_rows(
        trade_date=trade_date,
        portfolio_state=state,
        source="mtm_backfill",
    )

    _emit("rebalance", "Rebalancing paper portfolio…")
    before = compute_daily_metrics(state, prices)
    rebalance = rebalance_to_target_weights(
        state,
        target_weights=targets,
        prices=prices,
        exec_params=ExecutionParams(),
    )
    after = compute_daily_metrics(state, prices)

    _save_state(state_path, state)
    snapshot_path = _PROJECT_ROOT / "results" / f"paper_snapshot_{trade_date}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "date": trade_date,
                "before": before,
                "after": after,
                "rebalance": rebalance,
                "targets": targets,
                "candidates": candidate_set,
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
            trades_count=len(rebalance.get("trades") or []),
            source=history_source,
            holdings_weights=dict(state.weights(prices)),
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
            "candidate_count": len(candidate_set),
            "backfilled_days": int(backfill_info.get("backfilled_days", 0)),
            "backfill_start": backfill_info.get("backfill_start"),
            "backfill_end": backfill_info.get("backfill_end"),
            "backfill_warnings": backfill_info.get("warnings", []),
        },
        "before": before,
        "after": after,
        "rebalance": rebalance,
        "targets": targets,
        "candidates": candidate_set,
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
        default=str(_PROJECT_ROOT / "results" / "paper_state.json"),
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
        history_source="daily_cli",
    )


if __name__ == "__main__":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    main()
