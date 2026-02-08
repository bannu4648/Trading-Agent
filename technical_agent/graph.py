"""LangGraph workflow for the technical analyst agent."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from .config import AgentConfig
from .llm import get_llm
from .models import TechnicalState
from .prompts import TECHNICAL_SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from .tools import compute_indicators, fetch_ohlcv_data, generate_signals
from .utils.serialization import dumps_json


def _append_errors(state: TechnicalState, new_errors: List[str]) -> List[str]:
    errors = list(state.get("errors", []))
    errors.extend(new_errors)
    return errors


def _build_snapshot(df: pd.DataFrame) -> Dict[str, object]:
    if df.empty:
        return {}
    last = df.dropna().iloc[-1] if not df.dropna().empty else df.iloc[-1]
    timestamp = last.name
    values = {col: last[col] for col in df.columns}
    return {"timestamp": timestamp, "values": values}


def _rule_based_summary(signals: List[dict]) -> str:
    if not signals:
        return "No rule-based signals triggered in the latest bar."
    bulls = sum(1 for s in signals if s.get("direction") == "bullish")
    bears = sum(1 for s in signals if s.get("direction") == "bearish")
    neutrals = sum(1 for s in signals if s.get("direction") == "neutral")
    return (
        f"Signals: {bulls} bullish, {bears} bearish, {neutrals} neutral. "
        "Review indicator context for confirmation."
    )


def build_graph(agent_config: AgentConfig):
    llm = None
    if agent_config.enable_llm_summary:
        llm = get_llm(agent_config.llm)

    def fetch_data_node(state: TechnicalState) -> TechnicalState:
        request = state.get("request", {})
        errors: List[str] = []
        try:
            data = fetch_ohlcv_data(
                tickers=request.get("tickers", []),
                start_date=request.get("start_date"),
                end_date=request.get("end_date"),
                interval=request.get("interval", agent_config.data.interval),
                auto_adjust=agent_config.data.auto_adjust,
                prepost=agent_config.data.prepost,
            )
        except Exception as exc:
            data = {}
            errors.append(f"data_fetch_error:{exc}")
        return {"raw_data": data, "errors": _append_errors(state, errors)}

    def indicator_node(state: TechnicalState) -> TechnicalState:
        raw_data = state.get("raw_data", {})
        indicators: Dict[str, pd.DataFrame] = {}
        snapshots: Dict[str, Dict[str, object]] = {}
        errors: List[str] = []
        for symbol, df in raw_data.items():
            try:
                ind_df = compute_indicators(df, agent_config.indicators)
                indicators[symbol] = ind_df
                snapshots[symbol] = _build_snapshot(ind_df)
            except Exception as exc:
                errors.append(f"{symbol}:indicator_error:{exc}")
        return {
            "indicators": indicators,
            "snapshots": snapshots,
            "errors": _append_errors(state, errors),
        }

    def signal_node(state: TechnicalState) -> TechnicalState:
        indicators = state.get("indicators", {})
        signals, signal_errors = generate_signals(
            indicators, agent_config.signals, agent_config.extra_signal_modules
        )
        return {
            "signals": signals,
            "errors": _append_errors(state, signal_errors),
        }

    def summary_node(state: TechnicalState) -> TechnicalState:
        summaries: Dict[str, str] = {}
        snapshots = state.get("snapshots", {})
        signals = state.get("signals", {})
        errors: List[str] = []
        for symbol in signals:
            indicator_snapshot = snapshots.get(symbol, {})
            signals_list = signals.get(symbol, [])
            if llm is None:
                summaries[symbol] = _rule_based_summary(signals_list)
                continue
            prompt = build_summary_prompt(
                symbol=symbol,
                indicator_snapshot_json=dumps_json(indicator_snapshot, indent=2),
                signals_json=dumps_json(signals_list, indent=2),
            )
            try:
                response = llm.invoke(
                    [
                        SystemMessage(content=TECHNICAL_SUMMARY_SYSTEM_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                summaries[symbol] = response.content.strip()
            except Exception as exc:
                errors.append(f"{symbol}:llm_summary_error:{exc}")
                summaries[symbol] = _rule_based_summary(signals_list)
        return {"summaries": summaries, "errors": _append_errors(state, errors)}

    graph = StateGraph(TechnicalState)
    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("indicators", indicator_node)
    graph.add_node("signals", signal_node)
    graph.add_node("summary", summary_node)

    graph.add_edge("fetch_data", "indicators")
    graph.add_edge("indicators", "signals")
    graph.add_edge("signals", "summary")
    graph.add_edge("summary", END)

    graph.set_entry_point("fetch_data")
    return graph.compile()
