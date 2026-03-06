"""
tests/unit/test_social_agent.py
Unit tests for SocialSentimentAgent.
"""
import pytest
from unittest.mock import patch
from sentiment_agent.agents.social_sentiment_agent import SocialSentimentAgent


@pytest.fixture
def agent():
    return SocialSentimentAgent()


def test_agent_name(agent):
    assert agent.name == "social_sentiment"


def test_run_with_data(agent, sample_ticker, mock_gemini_positive):
    mock_social = {
        "ticker": "AAPL", "mentions": 245, "upvotes": 1820,
        "rank": 3, "rank_24h_ago": 7, "rank_change": 4,
    }
    with patch("agents.social_sentiment_agent.fetch_apewisdom", return_value=mock_social), \
         patch("agents.social_sentiment_agent.gemini_client.generate_json", return_value=mock_gemini_positive):
        result = agent.run(sample_ticker)

    assert -1.0 <= result["score"] <= 1.0
    assert result["label"] in ("positive", "negative", "neutral")
    assert result["mentions"] == 245
    assert result["upvotes"] == 1820


def test_run_zero_mentions(agent, sample_ticker, mock_gemini_neutral):
    mock_social = {
        "ticker": "AAPL", "mentions": 0, "upvotes": 0,
        "rank": 999, "rank_24h_ago": 999, "rank_change": 0,
    }
    with patch("agents.social_sentiment_agent.fetch_apewisdom", return_value=mock_social), \
         patch("agents.social_sentiment_agent.gemini_client.generate_json", return_value=mock_gemini_neutral):
        result = agent.run(sample_ticker)

    assert result["label"] == "neutral"


def test_safe_run_on_exception(agent, sample_ticker):
    with patch("agents.social_sentiment_agent.fetch_apewisdom", side_effect=Exception("timeout")):
        result = agent._safe_run(sample_ticker)

    assert result["score"] == 0.0
    assert "error" in result
