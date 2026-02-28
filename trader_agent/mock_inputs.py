"""
Mock Research Team output for standalone Trader Agent testing.

Mirrors a realistic technology sector rebalancing scenario similar to the
AlphaAgents paper's 15-stock tech experiment, but condensed to 6 stocks for
quick iteration. Stocks were chosen to present varied signals, conviction
levels, and volatilities so all four sizing methods produce meaningfully
different results.
"""

from .models import ResearchTeamOutput, StockRecommendation

MOCK_RESEARCH_OUTPUT = ResearchTeamOutput(
    portfolio_cash_pct=0.10,
    recommendations=[
        StockRecommendation(
            ticker="NVDA",
            signal="BUY",
            conviction_score=9.2,
            expected_return=0.32,
            volatility=0.55,
            current_weight=0.05,
        ),
        StockRecommendation(
            ticker="MSFT",
            signal="BUY",
            conviction_score=8.5,
            expected_return=0.18,
            volatility=0.22,
            current_weight=0.15,
        ),
        StockRecommendation(
            ticker="AAPL",
            signal="BUY",
            conviction_score=7.0,
            expected_return=0.12,
            volatility=0.20,
            current_weight=0.10,
        ),
        StockRecommendation(
            ticker="META",
            signal="BUY",
            conviction_score=6.3,
            expected_return=0.22,
            volatility=0.38,
            current_weight=0.08,
        ),
        StockRecommendation(
            ticker="INTC",
            signal="SELL",
            conviction_score=7.8,
            expected_return=-0.15,
            volatility=0.30,
            current_weight=0.07,
        ),
        StockRecommendation(
            ticker="AMZN",
            signal="HOLD",
            conviction_score=5.5,
            expected_return=0.08,
            volatility=0.28,
            current_weight=0.12,
        ),
    ],
)
