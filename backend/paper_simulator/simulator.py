from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class PortfolioState:
    """
    Dollar-denominated portfolio with long/short support.

    Positions store number of shares; valuation uses provided close prices.
    """

    cash: float
    shares: dict[str, float] = field(default_factory=dict)

    def equity(self, prices: dict[str, float]) -> float:
        return float(self.cash + sum(self.shares.get(t, 0.0) * prices.get(t, 0.0) for t in self.shares))

    def weights(self, prices: dict[str, float]) -> dict[str, float]:
        eq = self.equity(prices)
        if eq == 0:
            return {t: 0.0 for t in self.shares}
        return {t: (self.shares.get(t, 0.0) * prices.get(t, 0.0)) / eq for t in self.shares}


@dataclass(frozen=True)
class ExecutionParams:
    slippage_bps: float = 2.0
    commission_per_trade: float = 0.0


def _apply_slippage(price: float, buy: bool, slippage_bps: float) -> float:
    slip = (slippage_bps / 1e4) * price
    return price + slip if buy else price - slip


def rebalance_to_target_weights(
    state: PortfolioState,
    target_weights: dict[str, float],
    prices: dict[str, float],
    exec_params: ExecutionParams = ExecutionParams(),
) -> dict[str, Any]:
    """
    Rebalance instantly at provided prices (close-to-close style).

    - Positive weight = long; negative weight = short.
    - Uses current equity as the sizing base.
    - Allows shorting by making shares negative.
    """
    # Filter target to tradable tickers with prices
    target = {t: float(w) for t, w in target_weights.items() if t in prices and prices[t] > 0}
    for t in list(state.shares.keys()):
        if t not in prices or prices[t] <= 0:
            # keep but cannot trade/price; ignore in this step
            pass

    eq = state.equity(prices)
    if eq <= 0:
        return {"trades": [], "equity": eq, "cash": state.cash, "error": "Non-positive equity"}

    # Current dollar exposures
    current_dollars = {t: state.shares.get(t, 0.0) * prices.get(t, 0.0) for t in set(state.shares) | set(target)}
    target_dollars = {t: target.get(t, 0.0) * eq for t in set(state.shares) | set(target)}

    trades = []
    for t in sorted(target_dollars.keys()):
        px = prices.get(t)
        if px is None or px <= 0:
            continue
        delta_dollars = target_dollars[t] - current_dollars.get(t, 0.0)
        if abs(delta_dollars) < 1e-6:
            continue

        buy = delta_dollars > 0
        exec_px = _apply_slippage(px, buy=buy, slippage_bps=exec_params.slippage_bps)
        delta_shares = delta_dollars / exec_px

        # Update state
        state.shares[t] = state.shares.get(t, 0.0) + delta_shares
        state.cash -= delta_shares * exec_px
        state.cash -= exec_params.commission_per_trade

        trades.append(
            {
                "ticker": t,
                "side": "BUY" if buy else "SELL",
                "price": float(exec_px),
                "shares": float(delta_shares),
                "notional": float(delta_shares * exec_px),
            }
        )

    return {"trades": trades, "equity": state.equity(prices), "cash": state.cash}


def compute_daily_metrics(state: PortfolioState, prices: dict[str, float]) -> dict[str, Any]:
    eq = state.equity(prices)
    w = state.weights(prices)
    long_gross = sum(v for v in w.values() if v > 0)
    short_gross = -sum(v for v in w.values() if v < 0)
    net = long_gross - short_gross
    return {
        "equity": float(eq),
        "cash": float(state.cash),
        "gross_long": float(long_gross),
        "gross_short": float(short_gross),
        "net": float(net),
        "n_positions": int(sum(1 for _t, sh in state.shares.items() if abs(sh) > 1e-9)),
    }


def prices_for_date(price_panel: pd.DataFrame, date: str) -> dict[str, float]:
    """
    Convenience helper: given a yfinance-style panel of Close prices (index=dates, columns=tickers),
    return {ticker: close} for one date.
    """
    row = price_panel.loc[date]
    if isinstance(row, pd.Series):
        return {str(k): float(v) for k, v in row.dropna().items()}
    # single column DataFrame
    return {str(c): float(row[c]) for c in row.columns}

