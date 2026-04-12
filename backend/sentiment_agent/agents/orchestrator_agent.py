"""
Thin wrapper around the LangGraph pipeline.
Just kicks off the graph and returns the final report dict.
"""
import logging

from sentiment_agent.agents.sentiment_graph import build_sentiment_graph
from sentiment_agent.config.settings import settings
from streaming_context import reset_stream_ticker, set_stream_ticker

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Invokes the compiled LangGraph and collects the final report.
    Full graph: news -> social -> analyst -> web -> debate -> aggregate -> summary -> report
    Fast graph (SENTIMENT_FAST_PIPELINE): news -> analyst -> stub -> aggregate -> summary -> report
    """

    def run(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        fast = bool(settings.sentiment_fast_pipeline)
        logger.info(
            f"Starting LangGraph sentiment pipeline for {ticker} (fast={fast})"
        )

        graph = build_sentiment_graph(fast=fast)
        tkn = set_stream_ticker(ticker)
        try:
            final_state = graph.invoke({"ticker": ticker})
        finally:
            reset_stream_ticker(tkn)

        report = final_state.get("report", {})
        agg = final_state.get("aggregation", {})
        logger.info(
            f"Pipeline complete for {ticker}: "
            f"{agg.get('sentiment_label')} "
            f"(score={agg.get('sentiment_score')}, "
            f"confidence={agg.get('confidence')})"
        )
        return report
