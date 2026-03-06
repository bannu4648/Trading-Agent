"""
tests/unit/test_analyst_agent.py
Unit tests for AnalystBuzzAgent.
"""
import pytest
from unittest.mock import patch
from sentiment_agent.agents.analyst_buzz_agent import AnalystBuzzAgent


@pytest.fixture
def agent():
    return AnalystBuzzAgent()


def test_agent_name(agent):
    assert agent.name == "analyst_buzz"


def test_run_with_data(agent, sample_ticker, mock_analyst_data, mock_gemini_positive):
    with patch("agents.analyst_buzz_agent.fetch_analyst_data", return_value=mock_analyst_data), \
         patch("agents.analyst_buzz_agent.gemini_client.generate_json", return_value=mock_gemini_positive):
        result = agent.run(sample_ticker)

    assert -1.0 <= result["score"] <= 1.0
    assert result["label"] in ("positive", "negative", "neutral")
    assert "reasoning" in result
    assert "buy_count" in result
    assert "consensus" in result


def test_run_no_data(agent, sample_ticker):
    empty = {
        "ticker": "AAPL", "recommendation_key": "none", "analyst_count": 0,
        "target_mean_price": None, "target_high_price": None, "target_low_price": None,
        "current_price": None, "recent_actions": [],
    }
    with patch("agents.analyst_buzz_agent.fetch_analyst_data", return_value=empty):
        result = agent.run(sample_ticker)

    assert result["score"] == 0.0
    assert result["label"] == "neutral"


def test_upgrade_downgrade_counting(agent, sample_ticker, mock_analyst_data, mock_gemini_positive):
    with patch("agents.analyst_buzz_agent.fetch_analyst_data", return_value=mock_analyst_data), \
         patch("agents.analyst_buzz_agent.gemini_client.generate_json", return_value=mock_gemini_positive):
        result = agent.run(sample_ticker)

    # Goldman = buy (1), Morgan Stanley = overweight (1), Barclays = hold (1)
    assert result["buy_count"] == 2
    assert result["hold_count"] == 1
    assert result["sell_count"] == 0


def test_safe_run_on_exception(agent, sample_ticker):
    with patch("agents.analyst_buzz_agent.fetch_analyst_data", side_effect=Exception("API error")):
        result = agent._safe_run(sample_ticker)

    assert result["score"] == 0.0
    assert "error" in result
