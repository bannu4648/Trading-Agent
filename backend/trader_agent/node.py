"""
LangGraph node wrapper for the Trader Agent.

Provides two things:

1. trader_node(state) — a LangGraph-compatible node function.
2. run_trader_for_pipeline(combined_results) — a plain function for run_analysis.py.

Note: current_weight is always assumed to be 0.0 for all tickers.
The Research Team never provides portfolio state; the Trader Agent always
proposes fresh allocations from zero.
"""

from __future__ import annotations

import logging
from typing import Any

from streaming_context import emit_stage

from .adapter import build_research_output
from .agent import run_trader_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def trader_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node function for the Trader Agent.

    Expected state keys:
        combined_results  (dict)  — full run_full_analysis() output
    Writes to state:
        trader_output     (dict)  — TraderOutput.model_dump()
    """
    combined_results = state.get("combined_results", {})

    if not combined_results.get("results"):
        logger.warning("[trader_node] No results in combined_results — skipping.")
        return {"trader_output": {}}

    try:
        research_output = build_research_output(combined_results)
        trader_output   = run_trader_agent(research_output)
        logger.info(
            f"[trader_node] Done. method={trader_output.sizing_method_chosen} "
            f"invested={trader_output.total_invested_pct:.1%} "
            f"orders={len(trader_output.orders)}"
        )
        return {"trader_output": trader_output.model_dump()}
    except Exception as exc:
        logger.error(f"[trader_node] Trader Agent failed: {exc}", exc_info=True)
        return {"trader_output": {"error": str(exc)}}


# ---------------------------------------------------------------------------
# Plain function for run_analysis.py
# ---------------------------------------------------------------------------

def run_trader_for_pipeline(
    combined_results: dict[str, Any],
    current_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Run the Trader Agent as a plain function call (no LangGraph needed).

    Args:
        combined_results: The full dict returned by run_full_analysis().
        current_weights:  Optional {ticker: weight} for live portfolio testing.
                          Leave as None (default 0.0) for testing from scratch.

    Returns:
        TraderOutput as a plain dict, or {"error": ...} if the agent failed.
    """
    try:
        emit_stage(
            pipeline="trader",
            label="Trader agent (ReAct + sizing tools)",
            ticker=None,
        )
        research_output = build_research_output(combined_results, current_weights or {})
        trader_output   = run_trader_agent(research_output)
        logger.info(
            f"[trader_pipeline] Done. method={trader_output.sizing_method_chosen} "
            f"invested={trader_output.total_invested_pct:.1%}"
        )
        return trader_output.model_dump()
    except Exception as exc:
        logger.error(f"[trader_pipeline] Trader Agent failed: {exc}", exc_info=True)
        return {"error": str(exc)}
