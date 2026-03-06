"""
tests/integration/test_sentiment_graph.py
Integration tests for the LangGraph sentiment pipeline.
All Gemini calls are mocked — verifies graph structure, state flow, and final report.
"""
import pytest
from unittest.mock import patch, MagicMock
from sentiment_agent.agents.sentiment_graph import build_sentiment_graph, SentimentState


def _mock_agent_result(name, score=0.5, label="positive"):
    return {"score": score, "label": label, "reasoning": f"Mock {name}."}


def _mock_debate():
    return {
        "bull_case": "Strong earnings.",
        "bear_case": "EU risk.",
        "resolution": "Bullish dominates.",
        "key_drivers": ["earnings", "analyst upgrades"],
    }


@pytest.fixture
def graph():
    return build_sentiment_graph()


def test_graph_produces_report(graph):
    """Full graph run with all nodes mocked — final state must have a report."""
    with patch("agents.sentiment_graph._news_agent._safe_run",   return_value=_mock_agent_result("news")), \
         patch("agents.sentiment_graph._social_agent._safe_run", return_value=_mock_agent_result("social")), \
         patch("agents.sentiment_graph._analyst_agent._safe_run",return_value=_mock_agent_result("analyst")), \
         patch("agents.sentiment_graph._web_agent._safe_run",    return_value=_mock_agent_result("web")), \
         patch("agents.sentiment_graph._debate_agent.run",       return_value=_mock_debate()), \
         patch("agents.sentiment_graph.gemini_client.generate",  return_value="Great outlook."):

        final_state = graph.invoke({"ticker": "AAPL"})

    assert "report" in final_state
    report = final_state["report"]
    assert report["ticker"] == "AAPL"
    assert "sentiment_label" in report
    assert "sentiment_score" in report
    assert "debate" in report
    assert report["summary"] == "Great outlook."


def test_graph_state_flows_correctly(graph):
    """Each node's output should be present in the final state."""
    with patch("agents.sentiment_graph._news_agent._safe_run",   return_value=_mock_agent_result("news", 0.7)), \
         patch("agents.sentiment_graph._social_agent._safe_run", return_value=_mock_agent_result("social", 0.4)), \
         patch("agents.sentiment_graph._analyst_agent._safe_run",return_value=_mock_agent_result("analyst", 0.6)), \
         patch("agents.sentiment_graph._web_agent._safe_run",    return_value=_mock_agent_result("web", 0.3)), \
         patch("agents.sentiment_graph._debate_agent.run",       return_value=_mock_debate()), \
         patch("agents.sentiment_graph.gemini_client.generate",  return_value="Summary."):

        final_state = graph.invoke({"ticker": "TSLA"})

    # All intermediate states should be populated
    assert final_state["news_result"]["score"] == 0.7
    assert final_state["social_result"]["score"] == 0.4
    assert final_state["analyst_result"]["score"] == 0.6
    assert final_state["web_result"]["score"] == 0.3
    assert final_state["debate_result"]["resolution"] == "Bullish dominates."
    assert "sentiment_score" in final_state["aggregation"]


def test_graph_ticker_uppercased(graph):
    """Ticker should be uppercased in the final report."""
    with patch("agents.sentiment_graph._news_agent._safe_run",   return_value=_mock_agent_result("news")), \
         patch("agents.sentiment_graph._social_agent._safe_run", return_value=_mock_agent_result("social")), \
         patch("agents.sentiment_graph._analyst_agent._safe_run",return_value=_mock_agent_result("analyst")), \
         patch("agents.sentiment_graph._web_agent._safe_run",    return_value=_mock_agent_result("web")), \
         patch("agents.sentiment_graph._debate_agent.run",       return_value=_mock_debate()), \
         patch("agents.sentiment_graph.gemini_client.generate",  return_value="Summary."):

        # Pass lowercase ticker via orchestrator (which uppercases it)
        from sentiment_agent.agents.orchestrator_agent import OrchestratorAgent
        report = OrchestratorAgent().run("aapl")

    assert report["ticker"] == "AAPL"


def test_graph_sentiment_label_valid(graph):
    """Sentiment label must be one of the three valid values."""
    with patch("agents.sentiment_graph._news_agent._safe_run",   return_value=_mock_agent_result("news", 0.8)), \
         patch("agents.sentiment_graph._social_agent._safe_run", return_value=_mock_agent_result("social", 0.8)), \
         patch("agents.sentiment_graph._analyst_agent._safe_run",return_value=_mock_agent_result("analyst", 0.8)), \
         patch("agents.sentiment_graph._web_agent._safe_run",    return_value=_mock_agent_result("web", 0.8)), \
         patch("agents.sentiment_graph._debate_agent.run",       return_value=_mock_debate()), \
         patch("agents.sentiment_graph.gemini_client.generate",  return_value="Summary."):

        final_state = graph.invoke({"ticker": "AAPL"})

    assert final_state["report"]["sentiment_label"] in ("POSITIVE", "NEUTRAL", "NEGATIVE")


def test_graph_debate_section_in_report(graph):
    """Debate bull/bear/resolution must appear in the final report."""
    with patch("agents.sentiment_graph._news_agent._safe_run",   return_value=_mock_agent_result("news")), \
         patch("agents.sentiment_graph._social_agent._safe_run", return_value=_mock_agent_result("social")), \
         patch("agents.sentiment_graph._analyst_agent._safe_run",return_value=_mock_agent_result("analyst")), \
         patch("agents.sentiment_graph._web_agent._safe_run",    return_value=_mock_agent_result("web")), \
         patch("agents.sentiment_graph._debate_agent.run",       return_value=_mock_debate()), \
         patch("agents.sentiment_graph.gemini_client.generate",  return_value="Summary."):

        final_state = graph.invoke({"ticker": "AAPL"})

    debate = final_state["report"]["debate"]
    assert debate["bull_case"] == "Strong earnings."
    assert debate["bear_case"] == "EU risk."
    assert debate["resolution"] == "Bullish dominates."
    assert "earnings" in debate["key_drivers"]
