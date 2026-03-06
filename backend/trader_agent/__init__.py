"""Trader Agent — position sizing and trade order generation."""

from .adapter import build_research_output
from .agent import run_trader_agent
from .models import ResearchTeamOutput, StockRecommendation, TradeOrder, TraderOutput
from .node import run_trader_for_pipeline, trader_node

__all__ = [
    "build_research_output",
    "run_trader_agent",
    "run_trader_for_pipeline",
    "trader_node",
    "ResearchTeamOutput",
    "StockRecommendation",
    "TradeOrder",
    "TraderOutput",
]
