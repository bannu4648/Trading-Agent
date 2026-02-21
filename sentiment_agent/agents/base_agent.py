"""
Base class that all sentiment agents inherit from.

Each agent needs to implement run(ticker) which returns a dict with
at minimum: score (float, -1 to 1), label, reasoning, and agent name.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Every agent subclass must define a `name` property and a `run` method.
    The `_safe_run` wrapper catches exceptions so one failing agent
    doesn't take down the whole pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def run(self, ticker: str) -> dict:
        ...

    def _safe_run(self, ticker: str) -> dict:
        """Wraps run() so the orchestrator never crashes if an agent throws."""
        try:
            result = self.run(ticker)
            result["agent"] = self.name
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Error for {ticker}: {e}")
            return {
                "agent": self.name,
                "score": 0.0,
                "label": "neutral",
                "reasoning": f"Agent failed: {e}",
                "error": str(e),
            }
