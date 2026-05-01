"""
S&P 500 screened job: technicals on full universe → formula screen → deep research on candidates.

Used by FastAPI POST /api/analyze/sp500-screened. Mirrors ``run_top20_longshort_job`` after screening.
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

from paper_execution import extract_close_prices_from_technical, run_paper_rebalance_optional
from portfolio_validator import PortfolioValidator
from risk_portfolio_agent import RiskPortfolioAgent, RiskPortfolioConfig
from run_analysis import _run_fundamentals, _run_sentiment
from summarizer_agent import SummarizerAgent
from technical_agent.agent import TechnicalAnalystAgent
from technical_agent.config import config_from_env
from technical_agent.shared.serialization import to_serializable
from trader_agent.adapter import build_research_output
from trader_agent.agent import run_trader_from_allocator_targets
from trader_agent.models import ResearchTeamOutput
from universe.screen import select_candidates_by_expected_return
from universe.sp500 import get_sp500_tickers

logger = logging.getLogger("sp500_screened")

_MIN_WEIGHT = 1e-4


def run_sp500_screened(
    *,
    end_date: Optional[str] = None,
    start_date: Optional[str] = None,
    lookback_days: int = 365,
    interval: str = "1d",
    enable_llm_summary_technical: bool = False,
    candidate_pool_mult: int = 3,
    max_candidates: Optional[int] = 30,
    k_long: int = 10,
    k_short: int = 10,
    gross_long: float = 1.0,
    gross_short: float = 0.5,
    max_single_long: float = 0.05,
    max_single_short: float = 0.03,
    use_llm_interpret: bool = True,
    deep_sentiment: bool = True,
    deep_fundamentals: bool = True,
    deep_synthesis: bool = True,
    limit_universe: int = 0,
    output_dir: str = _DEFAULT_RESULTS_DIR,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    execute_paper: bool = False,
    paper_state_file: Optional[str] = None,
    paper_initial_cash: float = 100_000.0,
    paper_force: bool = False,
) -> Dict[str, Any]:
    tickers = [t.strip().upper() for t in get_sp500_tickers() if t.strip()]
    if limit_universe and limit_universe > 0:
        tickers = tickers[: int(limit_universe)]

    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if start_date is None:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_dt - timedelta(days=int(lookback_days))).strftime("%Y-%m-%d")

    n_universe = len(tickers)
    combined: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": [],
            "tickers_universe": tickers,
            "universe": "sp500_screened",
            "source": "live_rebalance",
            "as_of_end_date": end_date,
            "as_of_start_date": start_date,
            "research_total": 0,
            "research_done": 0,
            "pipeline_step": "init",
            "pipeline_step_label": "Starting…",
            "candidate_pool_mult": candidate_pool_mult,
            "max_candidates": max_candidates,
            "limit_universe": int(limit_universe),
            "enable_llm_summary_technical": enable_llm_summary_technical,
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

    # --- Phase 1: technical on full universe ---
    tech_output: Dict[str, Any] = {}
    try:
        _emit("technical_wide", f"Technical analysis ({n_universe} names, LLM summary={'on' if enable_llm_summary_technical else 'off'})…")
        tech_cfg = config_from_env()
        tech_cfg.enable_llm_summary = bool(enable_llm_summary_technical)
        tech_output = TechnicalAnalystAgent(config=tech_cfg).run(
            tickers, start_date=start_date, end_date=end_date, interval=interval
        )
        logger.info("SP500 screened: technical wide phase finished")
    except Exception as exc:
        logger.error("Technical (wide) failed: %s", exc)

    tech_by = tech_output.get("tickers", {}) if isinstance(tech_output, dict) else {}
    prices_map = extract_close_prices_from_technical(tech_by, tickers)
    tradable = [t for t in tickers if prices_map.get(t, 0.0) > 0]
    combined["metadata"]["tickers_tradable"] = tradable
    combined["metadata"]["tradable_count"] = len(tradable)
    _emit("technical_wide", f"Technical wide complete — {len(tradable)} tradable")

    # --- Phase 2: formula screen (full universe slice, not only names with a parsed close) ---
    # Missing/partial technicals still get formula ER/vol so max_candidates can be filled.
    wide_combined: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": tickers,
        },
        "results": {},
    }
    for t in tickers:
        wide_combined["results"][t] = {
            "technical": tech_by.get(t, {}),
            "sentiment": {},
            "fundamentals": {},
            "synthesis": "",
        }

    prelim = build_research_output(combined_results=wide_combined, current_weights=None, use_llm=False)
    candidates = select_candidates_by_expected_return(
        prelim.recommendations,
        k_long=k_long,
        k_short=k_short,
        pool_mult=candidate_pool_mult,
        max_candidates=max_candidates,
    )
    combined["metadata"]["candidates_screened"] = candidates
    combined["metadata"]["tickers"] = candidates
    n = len(candidates)
    nl = (n + 1) // 2
    combined["metadata"]["screened_long_tickers"] = candidates[:nl]
    combined["metadata"]["screened_short_tickers"] = candidates[nl:]
    combined["metadata"]["research_total"] = n
    combined["metadata"]["screen_universe_count"] = len(tickers)
    mc = int(max_candidates) if max_candidates is not None and max_candidates > 0 else None
    lu = int(limit_universe) if limit_universe and limit_universe > 0 else 0
    nt = len(tradable)
    reasons: List[str] = []
    if lu > 0:
        reasons.append(
            f"Universe is limited to the first {lu} S&P names (debug). Increase or clear "
            "'Limit universe' in the UI to run the full ~500 list."
        )
    if mc is not None and n < mc and lu == 0:
        if len(tickers) < mc:
            reasons.append(
                f"The universe has only {len(tickers)} tickers; cannot reach max_candidates={mc}."
            )
        else:
            reasons.append(
                f"Only {n} distinct tickers after the long/short screen split (max_candidates={mc}). "
                "This can happen when top and bottom halves overlap in a small universe."
            )
    combined["metadata"]["candidate_pool_shortfall_messages"] = reasons
    if nt < n:
        combined["metadata"]["pricing_note"] = (
            f"{nt} of {n} screened candidates have a usable close in technical output for paper rebalance; "
            "screening still used the full universe slice for ranking."
        )
    _emit("screen", f"Screened to {n} candidates")

    if not candidates:
        combined["target_weights"] = {}
        combined["trader"] = {
            "orders": [],
            "sizing_method_chosen": "none",
            "overall_rationale": "No candidates after screening.",
            "total_invested_pct": 0.0,
            "gross_short_pct": 0.0,
        }
        combined["risk_report"] = {
            "risk_level": "UNKNOWN",
            "warnings": ["Empty candidate set after screen"],
            "metrics": {},
        }
        combined["metadata"]["screened_candidate_count"] = 0
        combined["metadata"]["allocator_booked_count"] = 0
        combined["metadata"]["allocator_k_long"] = k_long
        combined["metadata"]["allocator_k_short"] = k_short
        combined["metadata"]["screened_long_tickers"] = []
        combined["metadata"]["screened_short_tickers"] = []
        combined["metadata"]["booked_tickers"] = []
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        out_path = os.path.join(output_dir, f"sp500_screened_{ts}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(combined, fh, default=to_serializable, indent=2)
        combined["metadata"]["saved_path"] = out_path
        return combined

    # --- Phase 3: deep research on candidates only ---
    for ticker in candidates:
        combined["results"][ticker] = {
            "technical": tech_by.get(ticker, {}),
            "sentiment": {},
            "fundamentals": {},
            "synthesis": "",
        }
        if deep_sentiment:
            try:
                combined["results"][ticker]["sentiment"] = _run_sentiment(ticker)
            except Exception as exc:
                logger.error("Sentiment failed for %s: %s", ticker, exc)
                combined["results"][ticker]["sentiment"] = {}
        if deep_fundamentals:
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

    summarizer = SummarizerAgent()
    if deep_synthesis:
        for ticker in candidates:
            try:
                combined["results"][ticker]["synthesis"] = summarizer.run(ticker, combined)
            except Exception as exc:
                logger.error("Synthesis failed for %s: %s", ticker, exc)
                combined["results"][ticker]["synthesis"] = "Synthesis unavailable."
            _emit("synthesis", f"Synthesis {ticker}")

    # --- Phase 4: adapter, allocator, trader, validation ---
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
    _emit("risk_portfolio", "Target weights computed")

    booked = {t for t, w in target_weights.items() if abs(float(w)) >= _MIN_WEIGHT}
    subset_recs = [r for r in recs.recommendations if r.ticker in booked]
    _emit("trader", f"Trader (allocator book, {len(subset_recs)} names)…")
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
            logger.error("Trader failed: %s", exc, exc_info=True)
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
            tech_by_ticker=tech_by,
            tickers_for_prices=tradable,
            risk_report=combined.get("risk_report"),
            state_path=state_path,
            initial_cash=paper_initial_cash,
            force=paper_force,
            as_of_date=as_of,
            history_source="live_rebalance",
        )
        _emit("paper", "Paper rebalance finished")

    n_booked = sum(1 for w in target_weights.values() if abs(float(w)) >= _MIN_WEIGHT)
    combined["metadata"]["screened_candidate_count"] = n
    combined["metadata"]["allocator_booked_count"] = n_booked
    combined["metadata"]["allocator_k_long"] = k_long
    combined["metadata"]["allocator_k_short"] = k_short

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = os.path.join(output_dir, f"sp500_screened_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, default=to_serializable, indent=2)
    combined["metadata"]["saved_path"] = out_path
    logger.info("Saved → %s", out_path)
    return combined
