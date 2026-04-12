"""
Optional paper rebalance after a pipeline job (no external broker).

Uses :func:`paper_simulator.simulator.rebalance_to_target_weights` with close
prices extracted from technical agent output.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RISK_BLOCK = "HIGH"


def extract_close_prices_from_technical(
    tech_by_ticker: Dict[str, Any],
    tickers: List[str],
) -> Dict[str, float]:
    """Match ``run_daily_paper_trade._extract_close_prices``."""
    prices: Dict[str, float] = {}
    for t in tickers:
        try:
            block = tech_by_ticker.get(t, {}) if isinstance(tech_by_ticker, dict) else {}
            ind = block.get("indicators", {})
            values = ind.get("values", ind)
            close = values.get("close") or values.get("Close")
            if close is None:
                continue
            prices[t] = float(close)
        except Exception:
            continue
    return prices


def run_paper_rebalance_optional(
    *,
    target_weights: Dict[str, float],
    tech_by_ticker: Dict[str, Any],
    tickers_for_prices: List[str],
    risk_report: Optional[Dict[str, Any]],
    state_path: str,
    initial_cash: float = 100_000.0,
    force: bool = False,
    as_of_date: Optional[str] = None,
    record_history: bool = True,
    history_source: str = "api_paper",
) -> Dict[str, Any]:
    """
    Load portfolio state, rebalance toward ``target_weights``, save state.

    Skips execution when validator reports ``risk_level == HIGH`` unless
    ``force`` is True.
    """
    from datetime import datetime, timezone

    from paper_simulator.simulator import (
        ExecutionParams,
        PortfolioState,
        compute_daily_metrics,
        rebalance_to_target_weights,
    )

    out: Dict[str, Any] = {"executed": False}

    if risk_report and not force:
        level = str(risk_report.get("risk_level", "")).upper()
        if level == _RISK_BLOCK:
            out["skipped"] = f"risk_level={level}; pass force=true to rebalance anyway"
            logger.warning("[paper] Skipped rebalance: %s", out["skipped"])
            return out

    path = Path(state_path)
    prices = extract_close_prices_from_technical(tech_by_ticker, tickers_for_prices)
    if not prices:
        out["error"] = "No close prices in technical output; cannot value portfolio"
        logger.error("[paper] %s", out["error"])
        return out

    trade_date = (as_of_date or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = PortfolioState(
            cash=float(payload.get("cash", initial_cash)),
            shares=dict(payload.get("shares", {})),
        )
    else:
        state = PortfolioState(cash=float(initial_cash), shares={})

    before_m = compute_daily_metrics(state, prices)
    rebalance = rebalance_to_target_weights(
        state,
        target_weights=target_weights,
        prices=prices,
        exec_params=ExecutionParams(),
    )
    after_m = compute_daily_metrics(state, prices)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"cash": state.cash, "shares": state.shares}, indent=2),
        encoding="utf-8",
    )
    out["executed"] = True
    out["state_path"] = str(path)
    out["rebalance"] = rebalance
    out["prices_used"] = len(prices)
    out["metrics_before"] = before_m
    out["metrics_after"] = after_m
    out["as_of_date"] = trade_date

    if record_history:
        try:
            from portfolio_history import append_paper_daily_row

            trades = rebalance.get("trades") or []
            hist = append_paper_daily_row(
                as_of_date=trade_date,
                equity_before=float(before_m["equity"]),
                equity_after=float(after_m["equity"]),
                cash_after=float(after_m["cash"]),
                n_positions=int(after_m["n_positions"]),
                gross_long=float(after_m["gross_long"]),
                gross_short=float(after_m["gross_short"]),
                trades_count=len(trades),
                source=history_source,
                holdings_weights=dict(state.weights(prices)),
            )
            out["history_record"] = hist
        except Exception as exc:
            logger.warning("[paper] history_record failed: %s", exc)
            out["history_error"] = str(exc)

    logger.info("[paper] Rebalance saved → %s (trades=%s)", path, len(rebalance.get("trades", [])))
    return out
