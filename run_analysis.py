"""
Unified orchestrator — runs both the technical and sentiment agents for the
same ticker(s) and saves a single combined JSON report.

Usage:
    python run_analysis.py --tickers META
    python run_analysis.py --tickers META,TSLA --output ./results
    python run_analysis.py --tickers AAPL --start 2025-01-01 --end 2025-06-01
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

# ── Technical agent imports ──
from technical_agent.agent import TechnicalAnalystAgent
from technical_agent.config import AgentConfig, config_from_env
from technical_agent.shared.serialization import to_serializable

# ── Sentiment agent imports ──
from sentiment_agent.agents.orchestrator_agent import OrchestratorAgent
from summarizer_agent import SummarizerAgent

# ── Trader agent imports ──
from trader_agent.node import run_trader_for_pipeline

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("unified_orchestrator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_tech_config() -> AgentConfig:
    """
    Build config for the technical agent from environment variables.
    Now that Groq is supported in the LLM factory, we just use
    config_from_env() which reads LLM_PROVIDER / GROQ_API_KEY from .env.
    """
    return config_from_env()


def _run_technical(tickers: List[str], start: str | None,
                   end: str | None, interval: str) -> Dict[str, Any]:
    """Run the technical agent and return its result dict."""
    logger.info("── Technical analysis ──")
    config = _build_tech_config()
    agent = TechnicalAnalystAgent(config=config)
    return agent.run(tickers, start_date=start, end_date=end, interval=interval)


def _run_sentiment(ticker: str) -> Dict[str, Any]:
    """Run the sentiment agent for a single ticker."""
    logger.info(f"── Sentiment analysis for {ticker} ──")
    return OrchestratorAgent().run(ticker)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_full_analysis(
    tickers: List[str],
    start_date: str | None = None,
    end_date: str | None = None,
    interval: str = "1d",
    output_dir: str = "./results",
) -> Dict[str, Any]:
    """Run both agents and merge their outputs into one JSON file."""

    # 1. Technical analysis (handles all tickers in one batch)
    tech_output = {}
    try:
        tech_output = _run_technical(tickers, start_date, end_date, interval)
    except Exception as exc:
        logger.error(f"Technical analysis failed: {exc}")

    # 2. Per-ticker sentiment analysis + merge
    combined: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": tickers,
        },
        "results": {},
    }

    for ticker in tickers:
        logger.info(f"Processing {ticker} …")

        # Extract technical result for this ticker
        ticker_tech = tech_output.get("tickers", {}).get(ticker, {})

        # Sentiment
        ticker_sentiment: Dict[str, Any] = {}
        try:
            ticker_sentiment = _run_sentiment(ticker)
        except Exception as exc:
            logger.error(f"Sentiment analysis failed for {ticker}: {exc}")

        combined["results"][ticker] = {
            "technical": ticker_tech,
            "sentiment": ticker_sentiment,
        }

    # 3. Final Synthesis (per-ticker summary)
    logger.info("── Final Synthesis ──")
    summarizer = SummarizerAgent()
    for ticker in tickers:
        try:
            summary = summarizer.run(ticker, combined)
            combined["results"][ticker]["synthesis"] = summary
        except Exception as exc:
            logger.error(f"Synthesis failed for {ticker}: {exc}")
            combined["results"][ticker]["synthesis"] = "Synthesis unavailable."

    # 4. Trader Agent — position sizing and trade order proposals
    logger.info("── Trader Agent ──")
    try:
        trader_result = run_trader_for_pipeline(combined)

        # Embed each ticker's order directly into its result dict
        for order in trader_result.get("orders", []):
            ticker = order.get("ticker")
            if ticker and ticker in combined["results"]:
                combined["results"][ticker]["trade_order"] = {
                    "action":             order.get("action"),
                    "proposed_weight":    order.get("proposed_weight"),
                    "weight_delta":       order.get("weight_delta"),
                    "sizing_method_used": order.get("sizing_method_used"),
                    "rationale":          order.get("rationale"),
                }

        # Keep top-level summary (method choice, overall rationale, total invested)
        combined["trader"] = {
            "sizing_method_chosen": trader_result.get("sizing_method_chosen"),
            "overall_rationale":    trader_result.get("overall_rationale"),
            "total_invested_pct":   trader_result.get("total_invested_pct"),
        }

        logger.info(
            f"Trader Agent complete. "
            f"method={trader_result.get('sizing_method_chosen', 'unknown')} "
            f"orders={len(trader_result.get('orders', []))}"
        )
    except Exception as exc:
        logger.error(f"Trader Agent failed: {exc}")
        combined["trader"] = {"error": str(exc)}

    # 5. Save
    os.makedirs(output_dir, exist_ok=True)
    safe_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    tickers_tag = "_".join(tickers[:5])
    output_file = os.path.join(output_dir, f"{tickers_tag}_{safe_ts}.json")

    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, default=to_serializable, indent=2)

    logger.info(f"✅ Combined analysis saved to: {output_file}")
    return combined


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Stock Analysis")
    parser.add_argument("--tickers", "-t", required=True,
                        help="Comma-separated ticker symbols")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--interval", default="1d", help="Data interval")
    parser.add_argument("--output", "-o", default="./results",
                        help="Output directory")

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
