from __future__ import annotations

from dataclasses import dataclass

from portfolio_longshort.allocator import LongShortAllocationParams, allocate_long_short
from trader_agent.models import ResearchTeamOutput, StockRecommendation


@dataclass(frozen=True)
class RiskPortfolioConfig:
    """
    Deterministic portfolio construction config.
    This is the "risk agent" layer that converts per-ticker recommendations into portfolio weights.
    """

    k_long: int = 25
    k_short: int = 25
    gross_long: float = 1.0
    gross_short: float = 0.5
    max_single_long: float = 0.05
    max_single_short: float = 0.03
    min_abs_position: float = 0.002


class RiskPortfolioAgent:
    def __init__(self, config: RiskPortfolioConfig | None = None) -> None:
        self.config = config or RiskPortfolioConfig()

    def build_target_weights(self, recommendations: list[StockRecommendation]) -> dict[str, float]:
        params = LongShortAllocationParams(
            k_long=self.config.k_long,
            k_short=self.config.k_short,
            gross_long=self.config.gross_long,
            gross_short=self.config.gross_short,
            max_single_long=self.config.max_single_long,
            max_single_short=self.config.max_single_short,
            min_abs_position=self.config.min_abs_position,
        )
        return allocate_long_short(recommendations, params=params)

    def run(self, research_output: ResearchTeamOutput) -> dict[str, float]:
        return self.build_target_weights(research_output.recommendations)

