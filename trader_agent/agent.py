"""
Trader Agent — LangChain ReAct agent powered by Groq.

Reads model configuration from the same .env the rest of the Trading-Agent
project uses (LLM_PROVIDER, GROQ_API_KEY, GROQ_MODEL).
"""

from __future__ import annotations

import json
import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from .models import ResearchTeamOutput, TradeOrder, TraderOutput
from .tools import (
    conviction_weight,
    equal_weight,
    generate_trade_orders,
    kelly_criterion_weight,
    volatility_adjusted_weight,
)

import logging
logger = logging.getLogger(__name__)


def _precompute_all_methods(recommendations_json: str) -> dict[str, dict]:
    """
    Run all four sizing tools deterministically in Python and return their
    weight outputs keyed by method name.  This guarantees the LLM always
    sees a full comparison rather than only the methods it happens to call.
    """
    results = {}
    for tool_fn, name in [
        (equal_weight,              "equal_weight"),
        (conviction_weight,         "conviction_weight"),
        (volatility_adjusted_weight,"volatility_adjusted_weight"),
        (kelly_criterion_weight,    "kelly_criterion_weight"),
    ]:
        try:
            raw = tool_fn.invoke({"recommendations_json": recommendations_json})
            results[name] = json.loads(raw)
        except Exception as exc:
            logger.warning(f"[precompute] {name} failed: {exc}")
            results[name] = {"method": name, "weights": {}, "error": str(exc)}
    return results

TRADER_SYSTEM_PROMPT = """You are the Trader Agent on a professional AI-powered trading desk.

Your role in the pipeline:
  Research Team → YOU (Trader Agent) → Risk Manager → Fund Manager

You will receive:
  1. The Research Team's stock recommendations (signals, conviction scores, expected returns, volatilities).
  2. Pre-computed weight allocations from ALL FOUR sizing methodologies, calculated deterministically in Python.

Your responsibilities:
1. Compare all four pre-computed weight sets side-by-side.
2. Select the single best methodology given the current batch characteristics:
   - equal_weight: simplest baseline, all BUY stocks get the same allocation
   - conviction_weight: higher conviction = larger allocation
   - volatility_adjusted_weight: risk-parity, each stock contributes equal risk
   - kelly_criterion_weight: mathematically optimal sizing via Kelly Criterion
3. Call generate_trade_orders ONCE with the weights from your chosen method to produce final orders.
4. Return a structured JSON response (TraderOutput format).

Selection guidelines:
- High volatility dispersion across stocks → prefer volatility_adjusted_weight (equalises risk contribution)
- High conviction dispersion (big gaps between scores) → prefer conviction_weight or kelly_criterion_weight
- Low dispersion in both dimensions → equal_weight is defensible and transparent
- Negative expected returns even for BUY signals → kelly_criterion_weight may assign 0, which is correct
- When in doubt between two methods, prefer the one that leaves more cash (lower total invested %)
  unless conviction is uniformly high (≥7/10 for most stocks)

Per-order rationale quality standard:
Each order's "rationale" must be 2-4 sentences covering ALL of the following:
  1. The Research Team's signal (BUY/SELL/HOLD) and conviction score (out of 10), and what they indicate.
  2. The key quantitative inputs: expected return and annualised volatility, and what they imply about risk/reward.
  3. Which sizing method was chosen and the precise weight it assigned — or, if 0%, why no capital is deployed.
  4. A qualitative judgement: high-confidence position, cautious trim, risk-management hold, etc.

TraderOutput schema:
{{
  "orders": [
    {{
      "ticker": "string",
      "action": "BUY" | "SELL" | "HOLD",
      "proposed_weight": float,
      "weight_delta": float,
      "sizing_method_used": "string",
      "rationale": "2-4 sentence professional narrative per the quality standard above"
    }}
  ],
  "sizing_method_chosen": "string",
  "overall_rationale": "string",
  "total_invested_pct": float
}}
"""

# Only generate_trade_orders is exposed — sizing is pre-computed in Python
TOOLS = [generate_trade_orders]


def build_agent_executor(temperature: float = 0.0) -> AgentExecutor:
    """
    Construct and return the LangChain AgentExecutor for the Trader Agent.

    Reads model name from GROQ_MODEL env var (set in .env alongside the rest
    of the Trading-Agent project). Falls back to llama-3.3-70b-versatile.
    """
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    llm = ChatGroq(
        model=model,
        temperature=temperature,
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", TRADER_SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm=llm, tools=TOOLS, prompt=prompt)

    return AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=True,
        max_iterations=10,
        return_intermediate_steps=True,
    )


def _extract_json(text: str) -> dict:
    """
    Robustly extract the first valid JSON object from an LLM response,
    regardless of whether it is wrapped in prose, markdown fences, or bare.
    """
    text = text.strip()

    # 1. Try the whole text first (bare JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip a leading ```json ... ``` or ``` ... ``` fence
    import re
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Find the first { ... } block in the text (handles leading prose)
    brace_start = text.find("{")
    if brace_start != -1:
        # Walk forward tracking depth to find the matching closing brace
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract JSON from LLM response:\n{text[:300]}")


def run_trader_agent(research_output: ResearchTeamOutput) -> TraderOutput:
    """
    Run the Trader Agent on a ResearchTeamOutput and return a structured TraderOutput.

    All four sizing methods are pre-computed in Python and passed to the LLM as
    context.  The LLM's role is purely to compare, select, and justify — it calls
    generate_trade_orders once with the chosen method's weights.

    Args:
        research_output: The full payload from the Research Team / adapter.

    Returns:
        A validated TraderOutput Pydantic object ready to be passed to the Risk Manager.
    """
    executor = build_agent_executor()

    input_payload = json.dumps(research_output.model_dump(), indent=2)
    recommendations_json = json.dumps(research_output.model_dump())

    # ── Deterministic pre-computation of all four methods ──
    all_methods = _precompute_all_methods(recommendations_json)
    methods_summary = json.dumps(all_methods, indent=2)
    logger.info(
        f"[trader] Pre-computed all 4 sizing methods: "
        + ", ".join(f"{k}→{list(v.get('weights', {}).values())}" for k, v in all_methods.items())
    )

    user_message = (
        f"Here is the Research Team's output for this rebalancing cycle:\n\n"
        f"{input_payload}\n\n"
        f"All four position sizing methods have already been computed for you:\n\n"
        f"{methods_summary}\n\n"
        f"Instructions:\n"
        f"1. Compare the four weight sets above side-by-side.\n"
        f"2. Select the single best method for this batch using the selection guidelines.\n"
        f"3. Call generate_trade_orders with the weights from your chosen method "
        f"   (pass the 'weights' dict from the method you selected as the weights_json argument).\n"
        f"4. Return your final response as a JSON object matching the TraderOutput schema."
    )

    result = executor.invoke({"input": user_message})
    raw_output: str = result["output"]

    output_dict = _extract_json(raw_output)

    orders = [TradeOrder(**o) for o in output_dict["orders"]]
    return TraderOutput(
        orders=orders,
        sizing_method_chosen=output_dict["sizing_method_chosen"],
        overall_rationale=output_dict["overall_rationale"],
        total_invested_pct=output_dict["total_invested_pct"],
    )
