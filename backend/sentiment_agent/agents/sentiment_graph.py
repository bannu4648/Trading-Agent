"""
LangGraph-based pipeline for sequential sentiment analysis.

Full pipeline: news -> social -> analyst -> web -> debate -> aggregate -> summary -> report

Fast pipeline (settings.sentiment_fast_pipeline): news -> analyst -> stub neutral
social/web + empty debate -> aggregate -> summary -> report — fewer LLM round-trips
for local Ollama / batch runs.
"""
from __future__ import annotations

import logging
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from sentiment_agent.agents.analyst_buzz_agent import AnalystBuzzAgent
from sentiment_agent.agents.aggregator_agent import AggregatorAgent
from sentiment_agent.agents.debate_agent import DebateAgent
from sentiment_agent.agents.news_sentiment_agent import NewsSentimentAgent
from sentiment_agent.agents.social_sentiment_agent import SocialSentimentAgent
from sentiment_agent.agents.web_sentiment_agent import WebSentimentAgent
from sentiment_agent.config.prompts import SUMMARY_PROMPT
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.output.report_generator import build_report

logger = logging.getLogger(__name__)

_SKIPPED = {
    "score": 0.0,
    "label": "neutral",
    "reasoning": "Skipped (SENTIMENT_FAST_PIPELINE=1).",
}


def _log_elapsed(node: str, t0: float) -> None:
    logger.info(f"[timing] sentiment.{node} {time.perf_counter() - t0:.2f}s")


class SentimentState(TypedDict):
    """Shared state dict that gets passed between all graph nodes."""

    ticker: str
    news_result: dict
    social_result: dict
    analyst_result: dict
    web_result: dict
    debate_result: dict
    aggregation: dict
    summary: str
    report: dict


_news_agent = NewsSentimentAgent()
_social_agent = SocialSentimentAgent()
_analyst_agent = AnalystBuzzAgent()
_web_agent = WebSentimentAgent()
_debate_agent = DebateAgent()
_aggregator = AggregatorAgent()


def news_node(state: SentimentState) -> dict:
    """Fetch headlines from Finviz + Yahoo and score them via LLM."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    logger.info(f"[news_node] Fetching news sentiment for {ticker}")
    result = _news_agent._safe_run(ticker)
    logger.info(f"[news_node] score={result.get('score', 0):.3f} label={result.get('label')}")
    _log_elapsed("news", t0)
    return {"news_result": result}


def social_node(state: SentimentState) -> dict:
    """Pull Reddit buzz from ApeWisdom and interpret it."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    logger.info(f"[social_node] Fetching social sentiment for {ticker}")
    result = _social_agent._safe_run(ticker)
    logger.info(f"[social_node] score={result.get('score', 0):.3f} label={result.get('label')}")
    _log_elapsed("social", t0)
    return {"social_result": result}


def analyst_node(state: SentimentState) -> dict:
    """Grab analyst recs from Finnhub (no cooldown needed, 60 calls/min)."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    logger.info(f"[analyst_node] Fetching analyst data for {ticker}")
    result = _analyst_agent._safe_run(ticker)
    logger.info(f"[analyst_node] score={result.get('score', 0):.3f} label={result.get('label')}")
    _log_elapsed("analyst", t0)
    return {"analyst_result": result}


def web_node(state: SentimentState) -> dict:
    """Search DuckDuckGo for recent articles and score the snippets."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    logger.info(f"[web_node] Fetching web sentiment for {ticker}")
    result = _web_agent._safe_run(ticker)
    logger.info(f"[web_node] score={result.get('score', 0):.3f} label={result.get('label')}")
    _log_elapsed("web", t0)
    return {"web_result": result}


def debate_node(state: SentimentState) -> dict:
    """Have the LLM synthesize a bull vs bear debate from all agent outputs."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    agent_results = {
        "news_sentiment": state.get("news_result", {}),
        "social_sentiment": state.get("social_result", {}),
        "analyst_buzz": state.get("analyst_result", {}),
        "web_search": state.get("web_result", {}),
    }
    logger.info(f"[debate_node] Running bull vs bear debate for {ticker}")
    result = _debate_agent.run(ticker, agent_results)
    logger.info(f"[debate_node] Resolution: {result.get('resolution', '')[:80]}")
    _log_elapsed("debate", t0)
    return {"debate_result": result}


def aggregate_node(state: SentimentState) -> dict:
    """Weighted score fusion. No LLM call, just math."""
    t0 = time.perf_counter()
    agent_results = {
        "news_sentiment": state.get("news_result", {}),
        "social_sentiment": state.get("social_result", {}),
        "analyst_buzz": state.get("analyst_result", {}),
        "web_search": state.get("web_result", {}),
    }
    aggregation = _aggregator.run(agent_results)
    logger.info(
        f"[aggregate_node] {aggregation['sentiment_label']} "
        f"score={aggregation['sentiment_score']} "
        f"confidence={aggregation['confidence']}"
    )
    _log_elapsed("aggregate", t0)
    return {"aggregation": aggregation}


def summary_node(state: SentimentState) -> dict:
    """Ask the LLM to write a short natural-language summary."""
    t0 = time.perf_counter()
    ticker = state["ticker"]
    aggregation = state.get("aggregation", {})
    debate = state.get("debate_result", {})

    prompt = SUMMARY_PROMPT.format(
        ticker=ticker,
        sentiment_score=aggregation.get("sentiment_score", 0.0),
        sentiment_label=aggregation.get("sentiment_label", "NEUTRAL"),
        confidence=aggregation.get("confidence", 0.0),
        resolution=debate.get("resolution", ""),
    )
    logger.info(f"[summary_node] Generating summary for {ticker}")
    try:
        summary = gemini_client.generate(prompt)
    except Exception as e:
        logger.error(f"[summary_node] Summary generation failed: {e}")
        summary = "Summary unavailable."
    _log_elapsed("summary", t0)
    return {"summary": summary}


def report_node(state: SentimentState) -> dict:
    """Package everything into the final JSON report. No LLM call."""
    t0 = time.perf_counter()
    agent_results = {
        "news_sentiment": state.get("news_result", {}),
        "social_sentiment": state.get("social_result", {}),
        "analyst_buzz": state.get("analyst_result", {}),
        "web_search": state.get("web_result", {}),
    }
    report = build_report(
        ticker=state["ticker"],
        agent_results=agent_results,
        aggregation=state.get("aggregation", {}),
        debate=state.get("debate_result", {}),
        summary=state.get("summary", ""),
    )
    _log_elapsed("report", t0)
    return {"report": report}


def fast_stub_node(state: SentimentState) -> dict:
    """Neutral social/web and empty debate so aggregate + summary can run without extra LLMs."""
    t0 = time.perf_counter()
    logger.info("[fast_stub_node] Skipping social, web, debate (fast pipeline)")
    out = {
        "social_result": dict(_SKIPPED),
        "web_result": dict(_SKIPPED),
        "debate_result": {
            "bull_case": "",
            "bear_case": "",
            "resolution": "",
            "key_drivers": [],
        },
    }
    _log_elapsed("fast_stub", t0)
    return out


def build_sentiment_graph(*, fast: bool = False):
    """Wire up the LangGraph with sequential edges and return the compiled graph."""
    graph = StateGraph(SentimentState)

    graph.add_node("news", news_node)
    graph.add_node("social", social_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("web", web_node)
    graph.add_node("debate", debate_node)
    graph.add_node("fast_stub", fast_stub_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("summary", summary_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "news")
    if fast:
        graph.add_edge("news", "analyst")
        graph.add_edge("analyst", "fast_stub")
        graph.add_edge("fast_stub", "aggregate")
    else:
        graph.add_edge("news", "social")
        graph.add_edge("social", "analyst")
        graph.add_edge("analyst", "web")
        graph.add_edge("web", "debate")
        graph.add_edge("debate", "aggregate")
    graph.add_edge("aggregate", "summary")
    graph.add_edge("summary", "report")
    graph.add_edge("report", END)

    return graph.compile()


sentiment_graph = build_sentiment_graph(fast=False)
