"""
LangGraph-based Fundamentals Agent implementation.
"""
from typing import Literal
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

try:
    from .state import FundamentalsAgentState
    from .tools import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
except ImportError:
    from state import FundamentalsAgentState
    from tools import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement


class FundamentalsAgent:
    """Fundamentals Analyst Agent using LangGraph."""
    
    def __init__(
        self,
        llm,
        max_iterations: int = 5,
        vendor: str = "yfinance",
        debug: bool = False,
    ):
        """
        Initialize the Fundamentals Agent.
        
        Args:
            llm: LangChain LLM instance (e.g., ChatOpenAI, ChatAnthropic)
            max_iterations: Maximum number of tool-calling iterations
            vendor: Data vendor to use ('yfinance' or 'alpha_vantage')
            debug: Enable debug mode for verbose output
        """
        self.llm = llm
        self.max_iterations = max_iterations
        self.vendor = vendor
        self.debug = debug
        
        # Create tools - vendor will be passed as parameter when tools are called
        self.tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Create tool node
        self.tool_node = ToolNode(self.tools)
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Compile with memory for state persistence
        memory = MemorySaver()
        self.app = self.graph.compile(checkpointer=memory)
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(FundamentalsAgentState)
        
        # Add nodes
        workflow.add_node("analyst", self._analyst_node)
        workflow.add_node("tools", self.tool_node)
        
        # Define edges
        workflow.set_entry_point("analyst")
        
        # Conditional edge: continue to tools if tool calls exist, else end
        workflow.add_conditional_edges(
            "analyst",
            self._should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )
        
        # After tools execute, always return to analyst for next iteration
        workflow.add_edge("tools", "analyst")
        
        return workflow
    
    def _analyst_node(self, state: FundamentalsAgentState) -> dict:
        """Main analyst node that generates analysis and tool calls."""
        ticker = state["ticker"]
        trade_date = state["trade_date"]
        messages = state.get("messages", [])
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", self.max_iterations)
        
        # Check iteration limit
        if iteration_count >= max_iterations:
            # Extract final report from last message if available
            if messages and isinstance(messages[-1], AIMessage):
                report = messages[-1].content
            else:
                report = "Analysis completed. Maximum iterations reached."
            
            return {
                "messages": messages,
                "fundamentals_report": report,
                "iteration_count": iteration_count + 1,
            }
        
        # Create system prompt
        system_message = (
            "You are a fundamental analyst researcher. You MUST use ALL four tools for every company "
            "to ensure complete, uniform reports: get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement. "
            "Call each tool once (use quarterly frequency for balance_sheet, cashflow, income_statement). "
            "Pass vendor='{}' for each tool.\n\n"
            "Write ONE comprehensive report with this EXACT structure (use these section headers):\n"
            "1. **Company Overview** - Name, sector, industry, share price, market cap, enterprise value. Include 'Data retrieved at' (from get_fundamentals) so readers know when the data was pulled.\n"
            "2. **Key Financial Metrics** - Present as a Markdown table. Include ALL of these when available: P/E, Forward P/E, PEG, "
            "Price/Book, Price/Sales, EV/Revenue, EV/EBITDA, Profit Margin, Operating Margin, ROE, ROA, Current Ratio, Quick Ratio, Debt/Equity, "
            "Cash per Share, Book Value. Use N/A only when the tool did not provide the value.\n"
            "3. **Balance Sheet Summary** - Key line items from get_balance_sheet in a clean Markdown table (e.g. Total Assets, "
            "Total Liabilities, Total Equity, Cash, Receivables). Use human-readable numbers (e.g. 1.23B, 456M); never use scientific notation.\n"
            "4. **Income Statement Summary** - Key line items from get_income_statement in a Markdown table (Revenue, COGS, "
            "Gross Profit, Operating Income, Net Income). Same number formatting.\n"
            "5. **Cash Flow Summary** - Key items from get_cashflow in a Markdown table (Operating, Investing, Financing, Net Change in Cash).\n"
            "6. **Growth and Valuation** - Revenue/Earnings growth, any trends from the data.\n"
            "7. **Summary Table** - A final Markdown table summarizing the most important metrics for the ticker.\n\n"
            "Rules: Do NOT paste raw tool output. Use the same units as in the tool output: B=billions, M=millions, T=trillions; "
            "for ratios and percentages use the value as given (e.g. 27.04% not 0.27). Never write values like '1,234M' or '1.5B' for "
            "cash per share (that is per-share, so a small number). Use 'N/A' only when the tool did not return that field. "
            "Keep report structure identical for every company. Current date: {}. Ticker: {}."
        ).format(
            self.vendor,
            trade_date, ticker
        )
        
        # Build prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_message),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        # Invoke LLM
        if not messages:
            # First iteration - create initial human message
            human_msg = HumanMessage(
                content=f"Analyze the fundamental data for {ticker} as of {trade_date}. "
                "Please gather comprehensive financial information and provide a detailed analysis."
            )
            messages = [human_msg]
        
        chain = prompt | self.llm_with_tools
        result = chain.invoke({"messages": messages})
        
        # Update messages
        updated_messages = list(messages) + [result]
        
        # Extract report if no tool calls (final response)
        report = ""
        if not result.tool_calls:
            report = result.content
        
        return {
            "messages": updated_messages,
            "fundamentals_report": report,
            "iteration_count": iteration_count + 1,
        }
    
    def _should_continue(self, state: FundamentalsAgentState) -> Literal["continue", "end"]:
        """Determine whether to continue to tools or end."""
        messages = state.get("messages", [])
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", self.max_iterations)
        
        # Check iteration limit
        if iteration_count >= max_iterations:
            return "end"
        
        # Check if last message has tool calls
        if messages:
            last_message = messages[-1]
            # If last message is an AI message with tool calls, go to tools
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "continue"
            # If last message is a tool message, we've executed tools, go back to analyst
            elif isinstance(last_message, ToolMessage):
                # This shouldn't happen here since tools node connects directly to analyst
                return "end"
            # If last message is AI without tool calls, we're done
            elif isinstance(last_message, AIMessage) and not last_message.tool_calls:
                return "end"
        
        # Default: end
        return "end"
    
    def analyze(
        self,
        ticker: str,
        trade_date: str,
        config: dict = None,
    ) -> dict:
        """
        Run the fundamentals analysis.
        
        Args:
            ticker: Stock ticker symbol
            trade_date: Trading date in YYYY-MM-DD format
            config: Optional LangGraph configuration
        
        Returns:
            Final state dictionary containing the analysis report
        """
        # Initialize state
        initial_state = {
            "ticker": ticker,
            "trade_date": trade_date,
            "messages": [],
            "agent_name": "Fundamentals Analyst",
            "fundamentals_report": "",
            "tool_calls_made": [],
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
        }
        
        # Prepare config
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        
        # Run the graph
        if self.debug:
            # Stream mode for debugging
            final_state = None
            for event in self.app.stream(initial_state, config=config):
                if self.debug:
                    print(f"\n--- Event: {list(event.keys())} ---")
                    for node_name, node_state in event.items():
                        if "messages" in node_state:
                            last_msg = node_state["messages"][-1]
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                print(f"Tool calls: {[tc['name'] for tc in last_msg.tool_calls]}")
                            elif hasattr(last_msg, "content"):
                                print(f"Content preview: {last_msg.content[:200]}...")
                final_state = node_state if node_state else final_state
        else:
            # Invoke mode
            final_state = self.app.invoke(initial_state, config=config)
        
        return final_state
    
    def get_report(self, state: dict) -> str:
        """Extract the fundamentals report from the final state."""
        report = state.get("fundamentals_report", "")
        
        # If no report in state, try to extract from last message
        if not report:
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage) and last_msg.content:
                    report = last_msg.content
        
        return report
