"""
tests/unit/test_debate_agent.py
Unit tests for DebateAgent.
"""
import pytest
from unittest.mock import patch
from sentiment_agent.agents.debate_agent import DebateAgent


@pytest.fixture
def agent():
    return DebateAgent()


def test_run_returns_required_fields(agent, sample_ticker, mock_agent_results, mock_debate_result):
    with patch("agents.debate_agent.gemini_client.generate_json", return_value=mock_debate_result):
        result = agent.run(sample_ticker, mock_agent_results)

    assert "bull_case" in result
    assert "bear_case" in result
    assert "resolution" in result
    assert "key_drivers" in result
    assert isinstance(result["key_drivers"], list)


def test_run_with_mixed_signals(agent, sample_ticker, mock_debate_result):
    mixed = {
        "news_sentiment": {"score": 0.6, "label": "positive", "reasoning": "Good news."},
        "social_sentiment": {"score": -0.4, "label": "negative", "reasoning": "Bearish Reddit."},
        "analyst_buzz": {"score": 0.3, "label": "positive", "reasoning": "Analyst upgrades."},
        "web_search": {"score": -0.2, "label": "negative", "reasoning": "Negative web coverage."},
    }
    with patch("agents.debate_agent.gemini_client.generate_json", return_value=mock_debate_result):
        result = agent.run(sample_ticker, mixed)

    assert result["bull_case"] != ""
    assert result["bear_case"] != ""


def test_graceful_fallback_on_gemini_error(agent, sample_ticker, mock_agent_results):
    """Debate agent should never crash — returns fallback on Gemini error."""
    with patch("agents.debate_agent.gemini_client.generate_json", side_effect=Exception("API error")):
        result = agent.run(sample_ticker, mock_agent_results)

    assert "bull_case" in result
    assert "bear_case" in result
    assert "resolution" in result


def test_key_drivers_is_list(agent, sample_ticker, mock_agent_results, mock_debate_result):
    with patch("agents.debate_agent.gemini_client.generate_json", return_value=mock_debate_result):
        result = agent.run(sample_ticker, mock_agent_results)

    assert isinstance(result["key_drivers"], list)
    assert len(result["key_drivers"]) <= 3
