"""Core models and shared types for the technical agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


@dataclass
class Signal:
    name: str
    symbol: str
    timestamp: str
    direction: str
    strength: float
    horizon: str
    rationale: str
    indicators: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndicatorSnapshot:
    symbol: str
    timestamp: str
    values: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TickerAnalysis:
    symbol: str
    indicators: IndicatorSnapshot
    signals: List[Dict[str, Any]]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentOutput:
    metadata: Dict[str, Any]
    request: Dict[str, Any]
    tickers: Dict[str, TickerAnalysis]
    handoff: Dict[str, Any]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "request": self.request,
            "tickers": {k: v.to_dict() for k, v in self.tickers.items()},
            "handoff": self.handoff,
            "errors": self.errors,
        }


class TechnicalState(TypedDict, total=False):
    request: Dict[str, Any]
    raw_data: Dict[str, Any]
    indicators: Dict[str, Any]
    snapshots: Dict[str, Dict[str, Any]]
    signals: Dict[str, List[Dict[str, Any]]]
    summaries: Dict[str, str]
    output: Dict[str, Any]
    errors: List[str]
