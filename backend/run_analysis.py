"""
Orchestrates the full analysis pipeline for one or more stock tickers.

Runs technical → sentiment → fundamentals → synthesis → trader → validation,
then writes a single combined JSON to the results folder.

Usage:
    python run_analysis.py --tickers AAPL,NVDA
    python run_analysis.py --tickers META,TSLA --output ./results
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure sibling agent packages are importable
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
_DEFAULT_RESULTS_DIR = os.path.join(_PROJECT_ROOT, "results")

# stdlib above, local project imports below
from technical_agent.agent import TechnicalAnalystAgent
from technical_agent.config import AgentConfig, config_from_env
from technical_agent.shared.serialization import to_serializable

from sentiment_agent.agents.orchestrator_agent import OrchestratorAgent
from summarizer_agent import SummarizerAgent

from fundamentals_agent.tools import fetch_fundamentals_data

from trader_agent.node import run_trader_for_pipeline
from trader_agent.adapter import build_research_output

from portfolio_validator import PortfolioValidator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")


# ---------------------------------------------------------------------------
# Agent runner helpers — thin wrappers so the main function stays readable
# ---------------------------------------------------------------------------

def _run_technical(
    tickers: List[str],
    start: str | None,
    end: str | None,
    interval: str,
) -> Dict[str, Any]:
    logger.info("[orchestrator] Running technical analysis")
    config = config_from_env()
    return TechnicalAnalystAgent(config=config).run(
        tickers, start_date=start, end_date=end, interval=interval
    )


def _run_sentiment(ticker: str) -> Dict[str, Any]:
    logger.info(f"[orchestrator] Sentiment → {ticker}")
    return OrchestratorAgent().run(ticker)


def _run_fundamentals(ticker: str) -> Dict[str, Any]:
    logger.info(f"[orchestrator] Fundamentals → {ticker}")
    try:
        return fetch_fundamentals_data(ticker, try_alpha_vantage=False)
    except Exception as exc:
        logger.error(f"[orchestrator] Fundamentals failed for {ticker}: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_full_analysis(
    tickers: List[str],
    start_date: str | None = None,
    end_date: str | None = None,
    interval: str = "1d",
    output_dir: str = _DEFAULT_RESULTS_DIR,
) -> Dict[str, Any]:
    """
    Full pipeline: technical → sentiment → fundamentals → synthesis →
    trader → portfolio validation → save JSON.

    Returns the combined results dict (same thing that gets saved).
    """

    # --- Step 1: Technical (batched for all tickers at once) ---
    tech_output: Dict[str, Any] = {}
    try:
        tech_output = _run_technical(tickers, start_date, end_date, interval)
    except Exception as exc:
        logger.error(f"[orchestrator] Technical analysis failed: {exc}")

    # Seed the combined dict — everything gets merged into this
    combined: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": tickers,
        },
        "results": {},
    }

    # --- Step 2: Per-ticker sentiment + fundamentals ---
    for ticker in tickers:
        logger.info(f"[orchestrator] Processing {ticker}")

        ticker_tech = tech_output.get("tickers", {}).get(ticker, {})

        ticker_sentiment: Dict[str, Any] = {}
        try:
            ticker_sentiment = _run_sentiment(ticker)
        except Exception as exc:
            logger.error(f"[orchestrator] Sentiment failed for {ticker}: {exc}")

        ticker_fundamentals: Dict[str, Any] = {}
        try:
            ticker_fundamentals = _run_fundamentals(ticker)
        except Exception as exc:
            logger.error(f"[orchestrator] Fundamentals failed for {ticker}: {exc}")

        combined["results"][ticker] = {
            "technical": ticker_tech,
            "sentiment": ticker_sentiment,
            "fundamentals": ticker_fundamentals,
        }

    # --- Step 3: Synthesis (one LLM call per ticker) ---
    logger.info("[orchestrator] Running synthesis")
    summarizer = SummarizerAgent()
    for ticker in tickers:
        try:
            combined["results"][ticker]["synthesis"] = summarizer.run(ticker, combined)
        except Exception as exc:
            logger.error(f"[orchestrator] Synthesis failed for {ticker}: {exc}")
            combined["results"][ticker]["synthesis"] = "Synthesis unavailable."

    # --- Step 4: Trader agent (position sizing + order proposals) ---
    logger.info("[orchestrator] Running trader agent")
    try:
        trader_result = run_trader_for_pipeline(combined)

        # Flatten each order into the per-ticker result for easy dashboard access
        for order in trader_result.get("orders", []):
            t = order.get("ticker")
            if t and t in combined["results"]:
                combined["results"][t]["trade_order"] = {
                    "action":             order.get("action"),
                    "proposed_weight":    order.get("proposed_weight"),
                    "weight_delta":       order.get("weight_delta"),
                    "sizing_method_used": order.get("sizing_method_used"),
                    "rationale":          order.get("rationale"),
                }

        combined["trader"] = {
            "sizing_method_chosen": trader_result.get("sizing_method_chosen"),
            "overall_rationale":    trader_result.get("overall_rationale"),
            "total_invested_pct":   trader_result.get("total_invested_pct"),
        }

        logger.info(
            f"[orchestrator] Trader done — "
            f"method={trader_result.get('sizing_method_chosen', 'unknown')} "
            f"orders={len(trader_result.get('orders', []))}"
        )
    except Exception as exc:
        logger.error(f"[orchestrator] Trader agent failed: {exc}")
        combined["trader"] = {"error": str(exc)}

    # --- Step 5: Portfolio validation (no LLM, just constraint checks) ---
    logger.info("[orchestrator] Running portfolio validation")
    try:
        all_orders = [
            {"ticker": t, **combined["results"][t]["trade_order"]}
            for t in tickers
            if "trade_order" in combined["results"].get(t, {})
        ]

        # Rebuild minimal recommendation list for the validator
        all_recs = [
            {"ticker": r.ticker, "conviction_score": r.conviction_score,
             "volatility": r.volatility, "signal": r.signal}
            for r in build_research_output(combined).recommendations
        ]

        validation = PortfolioValidator().validate(all_orders, all_recs)
        combined["risk_report"] = validation

        level = validation["risk_level"]
        logger.info(f"[orchestrator] Validation: {level} — {len(validation['warnings'])} warning(s)")
        for w in validation["warnings"]:
            logger.warning(f"[orchestrator] ⚠️  {w}")

    except Exception as exc:
        logger.error(f"[orchestrator] Portfolio validation failed: {exc}")
        combined["risk_report"] = {"risk_level": "UNKNOWN", "warnings": [str(exc)], "metrics": {}}

    # --- Step 6: Save to disk ---
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = os.path.join(output_dir, f"{'_'.join(tickers[:5])}_{ts}.json")

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, default=to_serializable, indent=2)

    logger.info(f"[orchestrator] ✅ Saved → {out_path}")
    return combined


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent stock analysis pipeline")
    parser.add_argument("--tickers", "-t", required=True, help="Comma-separated tickers e.g. AAPL,NVDA")
    parser.add_argument("--start",   help="Start date YYYY-MM-DD")
    parser.add_argument("--end",     help="End date YYYY-MM-DD")
    parser.add_argument("--interval", default="1d", help="Price interval (1d, 1wk...)")
    parser.add_argument("--output", "-o", default=_DEFAULT_RESULTS_DIR, help="Output directory")

    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    run_full_analysis(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        interval=args.interval,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
