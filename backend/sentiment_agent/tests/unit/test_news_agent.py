"""
tests/unit/test_news_agent.py
Unit tests for NewsSentimentAgent — all external calls are mocked.
"""
import pytest
from unittest.mock import patch, MagicMock
from sentiment_agent.agents.news_sentiment_agent import NewsSentimentAgent


@pytest.fixture
def agent():
    return NewsSentimentAgent()


def test_agent_name(agent):
    assert agent.name == "news_sentiment"


def test_run_with_headlines(agent, sample_ticker, mock_headlines, mock_gemini_positive):
    with patch("agents.news_sentiment_agent.fetch_all_headlines", return_value=mock_headlines), \
         patch("agents.news_sentiment_agent.gemini_client.generate_json", return_value=mock_gemini_positive):
        result = agent.run(sample_ticker)

    assert "score" in result
    assert "label" in result
    assert "reasoning" in result
    assert "sources" in result
    assert result["sources"] == len(mock_headlines)
    assert -1.0 <= result["score"] <= 1.0
    assert result["label"] in ("positive", "negative", "neutral")


def test_run_no_headlines(agent, sample_ticker):
    with patch("agents.news_sentiment_agent.fetch_all_headlines", return_value=[]):
        result = agent.run(sample_ticker)

    assert result["score"] == 0.0
    assert result["label"] == "neutral"
    assert result["sources"] == 0


def test_score_clamped(agent, sample_ticker, mock_headlines):
    """Score returned by Gemini should be clamped to [-1, 1]."""
    extreme = {"score": 5.0, "label": "positive", "reasoning": "Extreme."}
    with patch("agents.news_sentiment_agent.fetch_all_headlines", return_value=mock_headlines), \
         patch("agents.news_sentiment_agent.gemini_client.generate_json", return_value=extreme):
        result = agent.run(sample_ticker)

    assert result["score"] == 1.0


def test_safe_run_on_exception(agent, sample_ticker):
    """_safe_run should never raise; returns neutral on error."""
    with patch("agents.news_sentiment_agent.fetch_all_headlines", side_effect=Exception("network error")):
        result = agent._safe_run(sample_ticker)

    assert result["score"] == 0.0
    assert result["label"] == "neutral"
    assert "error" in result
