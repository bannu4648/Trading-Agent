"""
tests/conftest.py
Shared pytest fixtures and mock data for all tests.
"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_ticker():
    return "AAPL"


@pytest.fixture
def mock_headlines():
    return [
        "Apple reports record quarterly earnings, beats estimates",
        "iPhone sales surge in emerging markets",
        "Apple faces antitrust scrutiny in EU",
    ]


@pytest.fixture
def mock_apewisdom_response():
    return {
        "results": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "mentions": 245,
                "upvotes": 1820,
                "rank": 3,
                "rank_24h_ago": 7,
            }
        ]
    }


@pytest.fixture
def mock_analyst_data():
    return {
        "ticker": "AAPL",
        "recommendation_key": "buy",
        "analyst_count": 25,
        "target_mean_price": 210.0,
        "target_high_price": 240.0,
        "target_low_price": 175.0,
        "current_price": 195.0,
        "recent_actions": [
            {"firm": "Goldman Sachs", "to_grade": "Buy", "from_grade": "Neutral", "action": "up"},
            {"firm": "Morgan Stanley", "to_grade": "Overweight", "from_grade": "Overweight", "action": "main"},
            {"firm": "Barclays", "to_grade": "Hold", "from_grade": "Buy", "action": "down"},
        ],
    }


@pytest.fixture
def mock_web_snippets():
    return [
        "Apple stock rises on strong earnings: Analysts bullish on iPhone 17 cycle",
        "AAPL sees institutional buying as AI features drive upgrade cycle",
        "Apple faces EU fine but analysts say impact is minimal",
    ]


@pytest.fixture
def mock_gemini_positive():
    return {"score": 0.7, "label": "positive", "reasoning": "Strong earnings beat."}


@pytest.fixture
def mock_gemini_negative():
    return {"score": -0.5, "label": "negative", "reasoning": "Revenue miss."}


@pytest.fixture
def mock_gemini_neutral():
    return {"score": 0.05, "label": "neutral", "reasoning": "Mixed signals."}


@pytest.fixture
def mock_debate_result():
    return {
        "bull_case": "Strong earnings and analyst upgrades support positive outlook.",
        "bear_case": "EU regulatory risk and slowing growth in China.",
        "resolution": "Bullish sentiment dominates across most sources.",
        "key_drivers": ["Earnings beat", "Analyst upgrades", "Reddit buzz"],
    }


@pytest.fixture
def mock_agent_results():
    """Typical sentiment agent results for aggregator/debate tests."""
    return {
        "news_sentiment": {"score": 0.7, "label": "positive", "reasoning": "Positive news."},
        "social_sentiment": {"score": 0.4, "label": "positive", "reasoning": "High mentions.", "mentions": 245},
        "analyst_buzz": {"score": 0.6, "label": "positive", "reasoning": "Strong buy consensus.", "buy_count": 3, "hold_count": 1, "sell_count": 0},
        "web_search": {"score": 0.3, "label": "positive", "reasoning": "Positive web coverage.", "snippets_analyzed": 5},
    }
