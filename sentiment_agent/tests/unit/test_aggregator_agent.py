"""
tests/unit/test_aggregator_agent.py
Unit tests for the updated sentiment-only AggregatorAgent.
"""
import pytest
from sentiment_agent.agents.aggregator_agent import AggregatorAgent


@pytest.fixture
def agent():
    return AggregatorAgent()


def test_composite_score_range(agent, mock_agent_results):
    result = agent.run(mock_agent_results)
    assert -1.0 <= result["sentiment_score"] <= 1.0


def test_all_positive_gives_positive_label(agent):
    results = {
        "news_sentiment": {"score": 0.8, "label": "positive", "reasoning": ""},
        "social_sentiment": {"score": 0.7, "label": "positive", "reasoning": ""},
        "analyst_buzz": {"score": 0.6, "label": "positive", "reasoning": ""},
        "web_search": {"score": 0.5, "label": "positive", "reasoning": ""},
    }
    output = agent.run(results)
    assert output["sentiment_score"] > 0
    assert output["sentiment_label"] == "POSITIVE"


def test_all_negative_gives_negative_label(agent):
    results = {
        "news_sentiment": {"score": -0.8, "label": "negative", "reasoning": ""},
        "social_sentiment": {"score": -0.7, "label": "negative", "reasoning": ""},
        "analyst_buzz": {"score": -0.6, "label": "negative", "reasoning": ""},
        "web_search": {"score": -0.5, "label": "negative", "reasoning": ""},
    }
    output = agent.run(results)
    assert output["sentiment_score"] < 0
    assert output["sentiment_label"] == "NEGATIVE"


def test_mixed_signals_near_neutral(agent):
    results = {
        "news_sentiment": {"score": 0.5, "label": "positive", "reasoning": ""},
        "social_sentiment": {"score": -0.5, "label": "negative", "reasoning": ""},
        "analyst_buzz": {"score": 0.1, "label": "neutral", "reasoning": ""},
        "web_search": {"score": -0.1, "label": "neutral", "reasoning": ""},
    }
    output = agent.run(results)
    assert abs(output["sentiment_score"]) < 0.3


def test_output_has_required_fields(agent, mock_agent_results):
    result = agent.run(mock_agent_results)
    for field in ("sentiment_score", "sentiment_label", "confidence", "sources"):
        assert field in result


def test_sources_breakdown_has_all_agents(agent, mock_agent_results):
    result = agent.run(mock_agent_results)
    for key in ("news_sentiment", "social_sentiment", "analyst_buzz", "web_search"):
        assert key in result["sources"]


def test_confidence_range(agent, mock_agent_results):
    result = agent.run(mock_agent_results)
    assert 0.0 <= result["confidence"] <= 1.0


def test_mixed_signals_reduce_confidence(agent):
    """Mixed positive/negative signals should reduce confidence."""
    mixed = {
        "news_sentiment": {"score": 0.8, "label": "positive", "reasoning": ""},
        "social_sentiment": {"score": -0.8, "label": "negative", "reasoning": ""},
        "analyst_buzz": {"score": 0.0, "label": "neutral", "reasoning": ""},
        "web_search": {"score": 0.0, "label": "neutral", "reasoning": ""},
    }
    uniform = {
        "news_sentiment": {"score": 0.8, "label": "positive", "reasoning": ""},
        "social_sentiment": {"score": 0.8, "label": "positive", "reasoning": ""},
        "analyst_buzz": {"score": 0.8, "label": "positive", "reasoning": ""},
        "web_search": {"score": 0.8, "label": "positive", "reasoning": ""},
    }
    mixed_result = agent.run(mixed)
    uniform_result = agent.run(uniform)
    assert mixed_result["confidence"] <= uniform_result["confidence"]


def test_label_thresholds(agent):
    assert agent._score_to_label(0.20) == "POSITIVE"
    assert agent._score_to_label(-0.20) == "NEGATIVE"
    assert agent._score_to_label(0.10) == "NEUTRAL"
    assert agent._score_to_label(0.0) == "NEUTRAL"
