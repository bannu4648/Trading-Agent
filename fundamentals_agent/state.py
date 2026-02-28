"""
State definition for the Fundamentals Agent using LangGraph.
"""
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class FundamentalsAgentState(TypedDict):
    """State schema for the Fundamentals Agent graph."""
    
    # Input parameters
    ticker: Annotated[str, "Stock ticker symbol to analyze"]
    trade_date: Annotated[str, "Current trading date in YYYY-MM-DD format"]
    
    # Message history for LLM conversation
    messages: Annotated[Sequence[BaseMessage], "Conversation messages"]
    
    # Agent metadata
    agent_name: Annotated[str, "Name of the agent"]
    
    # Output report
    fundamentals_report: Annotated[str, "Comprehensive fundamentals analysis report"]
    
    # Tool call tracking
    tool_calls_made: Annotated[list, "List of tools that have been called"]
    
    # Iteration control
    iteration_count: Annotated[int, "Number of iterations/rounds completed"]
    max_iterations: Annotated[int, "Maximum number of iterations allowed"]
