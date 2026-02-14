"""Technical analyst agent orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import AgentConfig, config_from_env
from .graph import build_graph
from .integration import build_handoff_payload
from .models import AgentOutput, IndicatorSnapshot, TickerAnalysis
from .utils.serialization import to_serializable


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_tickers(tickers: List[str]) -> List[str]:
    return [t.strip().upper() for t in tickers if t and t.strip()]


class TechnicalAnalystAgent:
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self.config = config or config_from_env()
        self.graph = build_graph(self.config)

    def run(
        self,
        tickers: List[str],
        start_date: str | None,
        end_date: str | None,
        interval: str = "1d",
    ) -> Dict[str, Any]:
        request = {
            "tickers": _normalize_tickers(tickers),
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval,
        }
        state = self.graph.invoke({"request": request, "errors": []})
        return self._build_output(state, request)

    def _build_output(self, state: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        snapshots = state.get("snapshots", {})
        signals = state.get("signals", {})
        summaries = state.get("summaries", {})
        errors = state.get("errors", [])

        ticker_results: Dict[str, TickerAnalysis] = {}
        for symbol in request.get("tickers", []):
            snap = snapshots.get(symbol, {})
            indicator_snapshot = IndicatorSnapshot(
                symbol=symbol,
                timestamp=str(to_serializable(snap.get("timestamp", ""))),
                values=to_serializable(snap.get("values", {})),
            )
            ticker_results[symbol] = TickerAnalysis(
                symbol=symbol,
                indicators=indicator_snapshot,
                signals=signals.get(symbol, []),
                summary=summaries.get(symbol, ""),
            )

        metadata = {
            "generated_at": _utc_now_iso(),
            "llm_provider": self.config.llm.provider,
            "llm_model": self.config.llm.model,
        }

        output = AgentOutput(
            metadata=metadata,
            request=request,
            tickers=ticker_results,
            handoff=build_handoff_payload(
                {
                    "metadata": metadata,
                    "request": request,
                    "tickers": {k: v.to_dict() for k, v in ticker_results.items()},
                }
            ),
            errors=errors,
        )
        return output.to_dict()


def run_agent(
    tickers: List[str],
    start_date: str | None,
    end_date: str | None,
    interval: str = "1d",
    config: Optional[AgentConfig] = None,
) -> Dict[str, Any]:
    agent = TechnicalAnalystAgent(config=config)
    return agent.run(tickers, start_date, end_date, interval)
