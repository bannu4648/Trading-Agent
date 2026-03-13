"""
Thin wrapper around the LangGraph pipeline.
Just kicks off the graph and returns the final report dict.
"""
import logging
from sentiment_agent.agents.sentiment_graph import sentiment_graph

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Invokes the compiled LangGraph and collects the final report.
    The graph handles all the sequencing internally:
    news -> social -> analyst -> web -> debate -> aggregate -> summary -> report
    """

    def run(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        logger.info(f"Starting LangGraph sentiment pipeline for {ticker}")

        final_state = sentiment_graph.invoke({"ticker": ticker})

        report = final_state.get("report", {})
        agg = final_state.get("aggregation", {})
        logger.info(
            f"Pipeline complete for {ticker}: "
            f"{agg.get('sentiment_label')} "
            f"(score={agg.get('sentiment_score')}, "
            f"confidence={agg.get('confidence')})"
        )
        return report
