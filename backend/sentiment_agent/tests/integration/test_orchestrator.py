"""
tests/integration/test_orchestrator.py
Integration tests for OrchestratorAgent (LangGraph-backed).
Patches the compiled graph's invoke method to avoid real Gemini calls.
"""
import pytest
from unittest.mock import patch
from sentiment_agent.agents.orchestrator_agent import OrchestratorAgent


def _make_final_state(ticker="AAPL", score=0.5, label="POSITIVE"):
    """Simulate the final LangGraph state returned after all nodes run."""
    return {
        "ticker": ticker,
        "news_result":    {"score": score, "label": "positive", "reasoning": "Mock news."},
        "social_result":  {"score": score, "label": "positive", "reasoning": "Mock social."},
        "analyst_result": {"score": score, "label": "positive", "reasoning": "Mock analyst."},
        "web_result":     {"score": score, "label": "positive", "reasoning": "Mock web."},
        "debate_result": {
            "bull_case": "Strong.", "bear_case": "Weak.",
            "resolution": "Bullish.", "key_drivers": ["earnings"],
        },
        "aggregation": {
            "sentiment_score": score,
            "sentiment_label": label,
            "confidence": 0.75,
            "sources": {},
        },
        "summary": "Mock summary.",
        "report": {
            "ticker": ticker,
            "timestamp": "2026-02-18T10:00:00+00:00",
            "sentiment_label": label,
            "sentiment_score": score,
            "confidence": 0.75,
            "sources": {},
            "weights": {},
            "debate": {"bull_case": "Strong.", "bear_case": "Weak.", "resolution": "Bullish.", "key_drivers": []},
            "summary": "Mock summary.",
        },
    }


@pytest.fixture
def orchestrator():
    return OrchestratorAgent()


def test_report_has_required_fields(orchestrator):
    with patch("agents.orchestrator_agent.sentiment_graph.invoke",
               return_value=_make_final_state()):
        report = orchestrator.run("AAPL")

    required = ["ticker", "timestamp", "sentiment_label", "sentiment_score",
                "confidence", "sources", "weights", "debate", "summary"]
    for field in required:
        assert field in report, f"Missing field: {field}"


def test_sentiment_label_is_valid_enum(orchestrator):
    with patch("agents.orchestrator_agent.sentiment_graph.invoke",
               return_value=_make_final_state(label="POSITIVE")):
        report = orchestrator.run("AAPL")

    assert report["sentiment_label"] in ("POSITIVE", "NEUTRAL", "NEGATIVE")


def test_ticker_uppercased(orchestrator):
    state = _make_final_state(ticker="AAPL")
    with patch("agents.orchestrator_agent.sentiment_graph.invoke",
               return_value=state):
        report = orchestrator.run("aapl")

    assert report["ticker"] == "AAPL"


def test_sentiment_score_in_range(orchestrator):
    with patch("agents.orchestrator_agent.sentiment_graph.invoke",
               return_value=_make_final_state(score=0.6)):
        report = orchestrator.run("AAPL")

    assert -1.0 <= report["sentiment_score"] <= 1.0
    assert 0.0 <= report["confidence"] <= 1.0


def test_debate_section_present(orchestrator):
    with patch("agents.orchestrator_agent.sentiment_graph.invoke",
               return_value=_make_final_state()):
        report = orchestrator.run("AAPL")

    assert "debate" in report
    assert "bull_case" in report["debate"]
    assert "bear_case" in report["debate"]
    assert "resolution" in report["debate"]
