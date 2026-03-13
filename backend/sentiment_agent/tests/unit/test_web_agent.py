"""
tests/unit/test_web_agent.py
Unit tests for WebSentimentAgent.
"""
import pytest
from unittest.mock import patch
from sentiment_agent.agents.web_sentiment_agent import WebSentimentAgent


@pytest.fixture
def agent():
    return WebSentimentAgent()


def test_agent_name(agent):
    assert agent.name == "web_search"


def test_run_with_snippets(agent, sample_ticker, mock_web_snippets, mock_gemini_positive):
    with patch("agents.web_sentiment_agent.fetch_web_snippets", return_value=mock_web_snippets), \
         patch("agents.web_sentiment_agent.yf.Ticker") as mock_yf, \
         patch("agents.web_sentiment_agent.gemini_client.generate_json", return_value=mock_gemini_positive):
        mock_yf.return_value.info = {"shortName": "Apple Inc."}
        result = agent.run(sample_ticker)

    assert -1.0 <= result["score"] <= 1.0
    assert result["label"] in ("positive", "negative", "neutral")
    assert result["snippets_analyzed"] == len(mock_web_snippets)


def test_run_no_snippets(agent, sample_ticker):
    with patch("agents.web_sentiment_agent.fetch_web_snippets", return_value=[]), \
         patch("agents.web_sentiment_agent.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = {}
        result = agent.run(sample_ticker)

    assert result["score"] == 0.0
    assert result["label"] == "neutral"
    assert result["snippets_analyzed"] == 0


def test_score_clamped(agent, sample_ticker, mock_web_snippets):
    extreme = {"score": 99.0, "label": "positive", "reasoning": "Extreme."}
    with patch("agents.web_sentiment_agent.fetch_web_snippets", return_value=mock_web_snippets), \
         patch("agents.web_sentiment_agent.yf.Ticker") as mock_yf, \
         patch("agents.web_sentiment_agent.gemini_client.generate_json", return_value=extreme):
        mock_yf.return_value.info = {}
        result = agent.run(sample_ticker)

    assert result["score"] == 1.0


def test_safe_run_on_exception(agent, sample_ticker):
    with patch("agents.web_sentiment_agent.fetch_web_snippets", side_effect=Exception("timeout")), \
         patch("agents.web_sentiment_agent.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = {}
        result = agent._safe_run(sample_ticker)

    assert result["score"] == 0.0
    assert "error" in result
