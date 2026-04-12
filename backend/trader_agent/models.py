from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StockRecommendation(BaseModel):
    """A single stock recommendation produced by the Research Team."""

    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'AAPL'")
    signal: Literal["BUY", "SELL", "HOLD"] = Field(
        ..., description="Research Team's directional signal"
    )
    conviction_score: float = Field(
        ..., ge=0.0, le=10.0, description="Research Team confidence, 0 (low) to 10 (high)"
    )
    expected_return: float = Field(
        ..., description="Annualised expected return as a decimal, e.g. 0.15 for 15%"
    )
    volatility: float = Field(
        ..., gt=0.0, description="Annualised volatility as a decimal, e.g. 0.30 for 30%"
    )
    current_weight: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description=(
            "Current portfolio weight as a decimal. Positive = long, negative = short "
            "(e.g. 0.05 for +5% long, -0.02 for -2% short)."
        ),
    )


class ResearchTeamOutput(BaseModel):
    """Full payload handed off from the Research Team to the Trader Agent."""

    recommendations: list[StockRecommendation]
    portfolio_cash_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of portfolio currently held as cash",
    )


class TradeOrder(BaseModel):
    """A single proposed trade order produced by the Trader Agent."""

    ticker: str
    action: Literal["BUY", "SELL", "HOLD"]
    proposed_weight: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Target portfolio weight as a decimal after rebalancing (negative = short).",
    )
    weight_delta: float = Field(
        ..., description="Change in weight from current: positive = buy more, negative = sell"
    )
    sizing_method_used: str = Field(
        ..., description="Which position sizing method produced this weight"
    )
    rationale: str = Field(
        ..., description="LLM explanation for this specific order"
    )


class TraderOutput(BaseModel):
    """Full output from the Trader Agent, passed to the Risk Manager."""

    orders: list[TradeOrder]
    sizing_method_chosen: str = Field(
        ..., description="Primary sizing methodology selected by the agent"
    )
    overall_rationale: str = Field(
        ..., description="Narrative explaining the overall trading strategy for this batch"
    )
    total_invested_pct: float = Field(
        ...,
        description="Gross long exposure: sum of max(0, proposed_weight) across orders.",
    )
    gross_short_pct: float = Field(
        default=0.0,
        ge=0.0,
        description="Gross short exposure: sum of max(0, -proposed_weight) across orders.",
    )
