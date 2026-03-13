"""
Fundamentals agent package.

The pipeline only uses fetch_fundamentals_data from tools.py —
the LangGraph-based FundamentalsAgent class was the original standalone
version and is not wired into run_analysis.py.
"""
from .tools import fetch_fundamentals_data

__all__ = ["fetch_fundamentals_data"]
