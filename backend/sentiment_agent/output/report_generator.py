"""
Packages the final sentiment pipeline state into a clean report dict.

Called by report_node in sentiment_graph.py as the last step of the pipeline.
No LLM call — pure structural assembly of data already computed upstream.

The returned dict is what the rest of the project reads:
  - OrchestratorAgent.run() returns it directly
  - SummarizerAgent reads: sentiment_score, sentiment_label, confidence,
    sources, debate
  - Trader Agent adapter reads the same fields
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_report(
    ticker: str,
    agent_results: dict[str, Any],
    aggregation: dict[str, Any],
    debate: dict[str, Any],
    summary: str,
) -> dict[str, Any]:
    """
    Assemble the final sentiment report dict.

    Args:
        ticker:        Stock symbol, e.g. "AAPL"
        agent_results: Dict of individual agent outputs keyed by agent name:
                         news_sentiment, social_sentiment, analyst_buzz, web_search
        aggregation:   Weighted composite score from AggregatorAgent:
                         sentiment_score, sentiment_label, confidence, sources
        debate:        Bull vs bear synthesis from DebateAgent:
                         bull_case, bear_case, resolution, key_drivers
        summary:       Natural language summary string from the LLM summary node

    Returns:
        A flat report dict consumed by SummarizerAgent and the Trader Agent adapter.
    """
    return {
        "ticker":           ticker.upper(),
        "timestamp":        datetime.now(timezone.utc).isoformat(),

        # Top-level scores (read directly by SummarizerAgent + adapter)
        "sentiment_score":  aggregation.get("sentiment_score", 0.0),
        "sentiment_label":  aggregation.get("sentiment_label", "NEUTRAL"),
        "confidence":       aggregation.get("confidence", 0.0),

        # Per-source breakdown
        "sources":          agent_results,

        # Bull vs bear debate
        "debate":           debate,

        # Natural language summary
        "summary":          summary,
    }
