# Architecture Overview

## LangGraph Implementation

This fundamentals agent is built using **LangGraph**, a framework for building stateful, multi-actor applications with LLMs. Unlike the original TradingAgents implementation which uses a simpler function-based approach, this implementation leverages LangGraph's powerful state management and workflow orchestration.

## Key Components

### 1. State Management (`state.py`)

The `FundamentalsAgentState` TypedDict defines the complete state schema:

- **Input**: `ticker`, `trade_date`
- **Messages**: Conversation history for the LLM
- **Output**: `fundamentals_report`
- **Control**: `iteration_count`, `max_iterations`, `tool_calls_made`

This explicit state definition enables:
- Type safety
- State persistence (via checkpointer)
- Easy debugging and inspection
- Integration with other agents

### 2. Agent Graph (`agent.py`)

The `FundamentalsAgent` class builds a LangGraph `StateGraph`:

```
START → Analyst Node → [Has Tool Calls?] → Tools Node → Analyst Node → ... → END
```

**Nodes:**
- **Analyst Node**: LLM-powered analysis that decides which tools to call
- **Tools Node**: Executes tool calls (data retrieval)

**Edges:**
- **Conditional Edge**: Analyst → Tools (if tool calls exist) or END (if done)
- **Direct Edge**: Tools → Analyst (always return to analyst after tool execution)

**Features:**
- Iterative tool calling with configurable limits
- Automatic state management
- Debug mode with streaming output
- Checkpointing for state persistence

### 3. Tools (`tools.py`)

Four LangChain tools for data retrieval:

1. **get_fundamentals**: Company overview, metrics, ratios
2. **get_balance_sheet**: Balance sheet data (annual/quarterly)
3. **get_cashflow**: Cash flow statements
4. **get_income_statement**: Income statements

**Multi-Vendor Support:**
- yfinance (default, free, no API key)
- Alpha Vantage (requires API key, more comprehensive)

Each tool accepts a `vendor` parameter to choose the data source.

### 4. Configuration (`config.py`)

LLM client factory supporting:
- OpenAI (GPT-4, GPT-4o, GPT-3.5-turbo)
- Anthropic (Claude 3 Opus, Sonnet, Haiku)
- Google (Gemini Pro, Ultra)

Configuration is environment-based and easily extensible.

## Workflow Details

### Execution Flow

1. **Initialization**
   - Create LLM client
   - Bind tools to LLM
   - Build LangGraph workflow
   - Compile with memory checkpointer

2. **Analysis Execution**
   ```
   Initial State → Analyst Node
                    ↓
              [Generate Analysis]
                    ↓
         [Decide: Tools Needed?]
                    ↓
         Yes → Tools Node → Execute Tools
                    ↓
              Return to Analyst
                    ↓
         [More Analysis Needed?]
                    ↓
         Yes → Continue | No → END
   ```

3. **Tool Calling Pattern**
   - Analyst generates tool calls based on analysis needs
   - Tools execute and return data
   - Analyst processes data and generates insights
   - Iterates until comprehensive analysis complete

### State Transitions

```
State 0: {ticker, trade_date, messages: [], report: ""}
    ↓
State 1: {messages: [HumanMessage, AIMessage(tool_calls)], ...}
    ↓
State 2: {messages: [...ToolMessages], ...}
    ↓
State 3: {messages: [...AIMessage(analysis)], report: "..."}
    ↓
Final: {report: "comprehensive analysis", ...}
```

## Differences from Original TradingAgents

| Aspect | Original | This Implementation |
|--------|----------|---------------------|
| Framework | Simple function | LangGraph StateGraph |
| State Management | Implicit | Explicit TypedDict |
| Workflow | Linear | Graph-based with conditionals |
| Tool Calling | Single pass | Iterative with limits |
| Persistence | None | Checkpointer support |
| Standalone | No (part of system) | Yes (can run independently) |
| Debugging | Limited | Stream mode + verbose |

## Advantages of LangGraph Approach

1. **Explicit State**: Clear state schema makes debugging easier
2. **Workflow Visualization**: Graph structure is easy to understand
3. **Extensibility**: Easy to add new nodes or modify workflow
4. **State Persistence**: Checkpointer enables resumable workflows
5. **Error Handling**: Better error recovery with state management
6. **Integration**: Can be composed with other LangGraph agents

## Extension Points

### Adding New Tools

```python
@tool
def get_new_data(ticker: str, ...) -> str:
    """New tool for additional data."""
    # Implementation
    pass

# Add to agent
agent.tools.append(get_new_data)
agent.llm_with_tools = agent.llm.bind_tools(agent.tools)
```

### Adding New Nodes

```python
def custom_node(state: FundamentalsAgentState) -> dict:
    """Custom processing node."""
    # Process state
    return {"messages": [...], ...}

workflow.add_node("custom", custom_node)
workflow.add_edge("analyst", "custom")
```

### Custom Workflows

```python
# Modify workflow structure
workflow.add_conditional_edges(
    "analyst",
    custom_decision_function,
    {"path1": "node1", "path2": "node2"}
)
```

## Performance Considerations

- **Iteration Limits**: Prevents infinite loops
- **Tool Caching**: Consider caching tool results for repeated calls
- **Parallel Tool Calls**: LangGraph supports parallel execution
- **Streaming**: Debug mode streams output for better UX

## Best Practices

1. **Set Reasonable Limits**: `max_iterations` prevents runaway execution
2. **Error Handling**: Tools should handle errors gracefully
3. **State Inspection**: Use debug mode to understand state transitions
4. **Vendor Selection**: Choose vendor based on data needs and API limits
5. **LLM Selection**: Use appropriate model for complexity vs cost tradeoff
