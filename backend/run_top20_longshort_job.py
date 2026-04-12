"""
Top-20 long/short pilot: full research stack + RiskPortfolioAgent + batched Trader on the book.

Used by FastAPI POST /api/analyze/top20-longshort and optional CLI.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
_DEFAULT_RESULTS_DIR = os.path.join(_PROJECT_ROOT, "results")

from portfolio_validator import PortfolioValidator
from risk_portfolio_agent import RiskPortfolioAgent, RiskPortfolioConfig
from run_analysis import _run_fundamentals, _run_sentiment, _run_technical
from summarizer_agent import SummarizerAgent
from technical_agent.shared.serialization import to_serializable
from trader_agent.adapter import build_research_output
from paper_execution import run_paper_rebalance_optional
from trader_agent.agent import run_trader_from_allocator_targets
from trader_agent.models import ResearchTeamOutput
from universe.top20 import get_top20_tickers

logger = logging.getLogger("top20_longshort")

_MIN_WEIGHT = 1e-4


def run_top20_longshort(
    *,
    tickers: Optional[List[str]] = None,
    end_date: Optional[str] = None,
    start_date: Optional[str] = None,
    lookback_days: int = 365,
    interval: str = "1d",
    use_llm_interpret: bool = True,
    k_long: int = 10,
    k_short: int = 10,
    gross_long: float = 1.0,
    gross_short: float = 0.5,
    max_single_long: float = 0.05,
    max_single_short: float = 0.03,
    output_dir: str = _DEFAULT_RESULTS_DIR,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    execute_paper: bool = False,
    paper_state_file: Optional[str] = None,
    paper_initial_cash: float = 100_000.0,
    paper_force: bool = False,
) -> Dict[str, Any]:
    tickers = [t.strip().upper() for t in (tickers or get_top20_tickers()) if t.strip()]
    n = len(tickers)

    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if start_date is None:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_dt - timedelta(days=int(lookback_days))).strftime("%Y-%m-%d")

    combined: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": tickers,
            "universe": "top20_longshort",
            "as_of_end_date": end_date,
            "as_of_start_date": start_date,
            "research_total": n,
            "research_done": 0,
            "pipeline_step": "init",
            "pipeline_step_label": "Starting…",
        },
        "results": {},
    }

    def _emit(step: str, label: str) -> None:
        combined["metadata"]["pipeline_step"] = step
        combined["metadata"]["pipeline_step_label"] = label
        if not progress_callback:
            return
        try:
            snap = json.loads(json.dumps(combined, default=to_serializable))
            progress_callback(snap)
        except Exception as exc:
            logger.warning("progress_callback failed: %s", exc)

    # --- Technical (batch) ---
    tech_output: Dict[str, Any] = {}
    try:
        _emit("technical", "Running technical analysis (20 names)…")
        tech_output = _run_technical(tickers, start_date, end_date, interval)
        logger.info("Technical phase finished for top-20 run")
    except Exception as exc:
        logger.error("Technical analysis failed: %s", exc)

    for t in tickers:
        combined["results"][t] = {
            "technical": tech_output.get("tickers", {}).get(t, {}),
        }
    _emit("technical", "Technical analysis complete")

    # --- Per-ticker sentiment + fundamentals ---
    for ticker in tickers:
        logger.info("Research → %s", ticker)
        combined["results"][ticker]["technical"] = tech_output.get("tickers", {}).get(ticker, {})
        try:
            combined["results"][ticker]["sentiment"] = _run_sentiment(ticker)
        except Exception as exc:
            logger.error("Sentiment failed for %s: %s", ticker, exc)
            combined["results"][ticker]["sentiment"] = {}
        try:
            combined["results"][ticker]["fundamentals"] = _run_fundamentals(ticker)
        except Exception as exc:
            logger.error("Fundamentals failed for %s: %s", ticker, exc)
            combined["results"][ticker]["fundamentals"] = {}
        combined["metadata"]["research_done"] = combined["metadata"].get("research_done", 0) + 1
        _emit(
            "research",
            f"Research {combined['metadata']['research_done']}/{n} — {ticker}",
        )

    # --- Synthesis ---
    summarizer = SummarizerAgent()
    for ticker in tickers:
        try:
            combined["results"][ticker]["synthesis"] = summarizer.run(ticker, combined)
        except Exception as exc:
            logger.error("Synthesis failed for %s: %s", ticker, exc)
            combined["results"][ticker]["synthesis"] = "Synthesis unavailable."
        _emit("synthesis", f"Synthesis {ticker}")

    # --- Adapter recommendations + risk portfolio weights ---
    _emit("risk_portfolio", "Building recommendations & target weights…")
    recs = build_research_output(combined, use_llm=use_llm_interpret)
    combined["recommendations_snapshot"] = [r.model_dump() for r in recs.recommendations]

    rp = RiskPortfolioAgent(
        RiskPortfolioConfig(
            k_long=min(k_long, n),
            k_short=min(k_short, n),
            gross_long=gross_long,
            gross_short=gross_short,
            max_single_long=max_single_long,
            max_single_short=max_single_short,
        )
    )
    target_weights = rp.build_target_weights(recs.recommendations)
    combined["target_weights"] = target_weights
    combined["risk_portfolio"] = {
        "k_long": k_long,
        "k_short": k_short,
        "gross_long": gross_long,
        "gross_short": gross_short,
    }
    booked_list = sorted(
        (t for t, w in target_weights.items() if abs(float(w)) >= _MIN_WEIGHT),
        key=lambda t: -abs(float(target_weights[t])),
    )
    combined["metadata"]["booked_tickers"] = booked_list
    combined["metadata"]["allocator_booked_count"] = len(booked_list)
    combined["metadata"]["allocator_k_long"] = k_long
    combined["metadata"]["allocator_k_short"] = k_short
    _emit("risk_portfolio", "Target weights computed")

    # --- Trader ReAct on booked names only ---
    booked = {t for t, w in target_weights.items() if abs(float(w)) >= _MIN_WEIGHT}
    subset_recs = [r for r in recs.recommendations if r.ticker in booked]
    _emit("trader", f"Trader agent ({len(subset_recs)} names in book)…")
    if subset_recs:
        try:
            sub = ResearchTeamOutput(recommendations=subset_recs, portfolio_cash_pct=0.0)
            book_weights = {t: float(target_weights[t]) for t in booked if t in target_weights}
            trader_model = run_trader_from_allocator_targets(sub, book_weights)
            trader_dict = trader_model.model_dump()
            combined["trader"] = trader_dict
            for order in trader_dict.get("orders", []):
                t = order.get("ticker")
                if t and t in combined["results"]:
                    combined["results"][t]["trade_order"] = {
                        "action": order.get("action"),
                        "proposed_weight": order.get("proposed_weight"),
                        "weight_delta": order.get("weight_delta"),
                        "sizing_method_used": order.get("sizing_method_used"),
                        "rationale": order.get("rationale"),
                    }
        except Exception as exc:
            logger.error("Trader agent failed: %s", exc, exc_info=True)
            combined["trader"] = {"error": str(exc)}
    else:
        combined["trader"] = {
            "orders": [],
            "sizing_method_chosen": "none",
            "overall_rationale": "No non-zero target weights from allocator.",
            "total_invested_pct": 0.0,
            "gross_short_pct": 0.0,
        }
    _emit("trader", "Trader complete")

    # --- Validation on allocator targets (long/short-aware) ---
    synthetic_orders: List[Dict[str, Any]] = []
    for t, w in target_weights.items():
        if abs(float(w)) < _MIN_WEIGHT:
            continue
        wf = float(w)
        synthetic_orders.append(
            {
                "ticker": t,
                "proposed_weight": wf,
                "action": "BUY" if wf > 0 else "SELL",
                "weight_delta": wf,
                "sizing_method_used": "risk_portfolio_agent",
                "rationale": "Allocator target weight.",
            }
        )
    all_recs = [
        {
            "ticker": r.ticker,
            "conviction_score": r.conviction_score,
            "volatility": r.volatility,
            "signal": r.signal,
        }
        for r in recs.recommendations
    ]
    try:
        combined["risk_report"] = PortfolioValidator().validate(synthetic_orders, all_recs)
    except Exception as exc:
        logger.error("Validation failed: %s", exc)
        combined["risk_report"] = {
            "risk_level": "UNKNOWN",
            "warnings": [str(exc)],
            "metrics": {},
        }
    _emit("validation", "Validation complete")

    if execute_paper:
        _emit("paper", "Paper rebalance (optional)…")
        state_path = paper_state_file or os.path.join(output_dir, "paper_state.json")
        as_of = combined["metadata"].get("as_of_end_date") or end_date
        combined["paper_execution"] = run_paper_rebalance_optional(
            target_weights=target_weights,
            tech_by_ticker=tech_output.get("tickers", {}) if isinstance(tech_output, dict) else {},
            tickers_for_prices=tickers,
            risk_report=combined.get("risk_report"),
            state_path=state_path,
            initial_cash=paper_initial_cash,
            force=paper_force,
            as_of_date=as_of,
            history_source="api_top20",
        )
        _emit("paper", "Paper rebalance finished")

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = os.path.join(output_dir, f"top20_longshort_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, default=to_serializable, indent=2)
    combined["metadata"]["saved_path"] = out_path
    logger.info("Saved → %s", out_path)
    return combined
