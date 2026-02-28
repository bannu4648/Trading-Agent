"""
Fundamentals Agent - A LangGraph-based agent for fundamental stock analysis.
"""
from .agent import FundamentalsAgent
from .state import FundamentalsAgentState
from .config import get_llm_client, DEFAULT_CONFIG
from .tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)

__all__ = [
    "FundamentalsAgent",
    "FundamentalsAgentState",
    "get_llm_client",
    "DEFAULT_CONFIG",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
]

__version__ = "1.0.0"
