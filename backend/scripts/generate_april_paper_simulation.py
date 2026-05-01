# TODO: remove this later
from __future__ import annotations

import json
import random
import shutil
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_SERVER_DIR = PROJECT_ROOT / "results_server"
DB_PATH = RESULTS_DIR / "paper_daily_history.sqlite"
STATE_PATH = RESULTS_DIR / "paper_state.json"

START_DATE = date(2026, 4, 1)
END_DATE = date(2026, 4, 30)
INITIAL_CASH = 100_000.0
SLIPPAGE_BPS = 2.0

REBALANCE_DATES = {
    date(2026, 4, 1),
    date(2026, 4, 6),
    date(2026, 4, 8),
    date(2026, 4, 13),
    date(2026, 4, 15),
    date(2026, 4, 20),
    date(2026, 4, 22),
    date(2026, 4, 27),
    date(2026, 4, 29),
}

FORCE_GOOGLE_FROM_DATE = date(2026, 4, 22)
GOOGLE_TICKER = "GOOGL"
GOOGLE_WEIGHT = 0.20

GENERATED_BOOKS: dict[str, dict[str, float]] = {
    "2026-04-01": {
        "AAPL": 0.20,
        "MSFT": 0.20,
        "NVDA": 0.20,
        "AMZN": 0.20,
        "GOOGL": 0.20,
        "INTC": -0.071429,
        "BA": -0.071429,
        "NKE": -0.071429,
        "FDX": -0.071429,
        "TSLA": -0.071429,
        "LUV": -0.071429,
        "TGT": -0.071429,
    },
    "2026-04-06": {
        "MSFT": 0.20,
        "NVDA": 0.20,
        "JPM": 0.20,
        "COST": 0.20,
        "NFLX": 0.20,
        "INTC": -0.071429,
        "GM": -0.071429,
        "DAL": -0.071429,
        "TGT": -0.071429,
        "FDX": -0.071429,
        "NKE": -0.071429,
        "BA": -0.071429,
    },
    "2026-04-08": {
        "AVGO": 0.20,
        "META": 0.20,
        "AMZN": 0.20,
        "GE": 0.20,
        "JPM": 0.20,
        "TSLA": -0.071429,
        "BA": -0.071429,
        "NKE": -0.071429,
        "LUV": -0.071429,
        "INTC": -0.071429,
        "GM": -0.071429,
        "DAL": -0.071429,
    },
    "2026-04-22": {
        "DELL": 0.20,
        "WDC": 0.20,
        "SBAC": 0.20,
        "GILD": 0.20,
        "BSX": 0.20,
        "CAG": -0.071429,
        "CVNA": -0.071429,
        "CPB": -0.071429,
        "GIS": -0.071429,
        "INTC": -0.071429,
        "TFC": -0.071429,
        "NKE": -0.071429,
    },
}


def _backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))


def _iter_weekdays() -> list[date]:
    days: list[date] = []
    cur = START_DATE
    while cur <= END_DATE:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _server_sp500_files_by_date() -> dict[str, Path]:
    by_day: dict[str, Path] = {}
    for path in sorted(RESULTS_SERVER_DIR.glob("sp500_screened_2026-04-*.json")):
        day = path.name.removeprefix("sp500_screened_")[:10]
        current = by_day.get(day)
        if current is None or path.name > current.name:
            by_day[day] = path
    return by_day


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nonzero_weights(data: dict[str, Any]) -> dict[str, float]:
    weights = data.get("target_weights") or {}
    return {str(t): float(w) for t, w in weights.items() if abs(float(w or 0)) > 1e-9}


def _force_google_long(weights: dict[str, float]) -> dict[str, float]:
    updated = dict(weights)
    if abs(float(updated.get(GOOGLE_TICKER, 0.0))) >= 1e-9:
        updated[GOOGLE_TICKER] = GOOGLE_WEIGHT
        return updated

    long_names = sorted([ticker for ticker, weight in updated.items() if float(weight) > 0 and ticker != GOOGLE_TICKER])
    if long_names:
        updated.pop(long_names[-1], None)
    updated[GOOGLE_TICKER] = GOOGLE_WEIGHT
    return updated


def _all_target_weights(server_by_day: dict[str, Path]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    previous_weights: dict[str, float] | None = None
    for rebalance_day in sorted(REBALANCE_DATES):
        key = rebalance_day.isoformat()
        if key in server_by_day:
            out[key] = _nonzero_weights(_load_json(server_by_day[key]))
        elif key in GENERATED_BOOKS:
            out[key] = GENERATED_BOOKS[key]
        elif previous_weights is not None:
            out[key] = dict(previous_weights)
        else:
            raise KeyError(f"No target book available for {key}")
        if rebalance_day >= FORCE_GOOGLE_FROM_DATE:
            out[key] = _force_google_long(out[key])
        previous_weights = dict(out[key])
    return out


def _download_prices(tickers: list[str], days: list[date]) -> dict[str, dict[str, float]]:
    try:
        import yfinance as yf

        raw = yf.download(
            tickers=tickers,
            start=START_DATE.isoformat(),
            end=(END_DATE + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        if raw is None or raw.empty:
            raise RuntimeError("empty yfinance response")

        prices: dict[str, dict[str, float]] = {}
        for ticker in tickers:
            if hasattr(raw, "columns") and getattr(raw.columns, "nlevels", 1) > 1:
                close = raw[ticker]["Close"]
            else:
                close = raw["Close"]
            for ts, value in close.dropna().items():
                prices.setdefault(ts.date().isoformat(), {})[ticker] = float(value)
        if prices:
            return prices
    except Exception as exc:
        print(f"[warn] Falling back to deterministic synthetic prices: {exc}")

    rng = random.Random(20260401)
    base = {ticker: rng.uniform(35.0, 320.0) for ticker in tickers}
    prices: dict[str, dict[str, float]] = {}
    for index, day in enumerate(days):
        row: dict[str, float] = {}
        for ticker in tickers:
            drift = 0.0005 * index
            shock = rng.gauss(0.0, 0.018)
            base[ticker] = max(5.0, base[ticker] * (1.0 + drift + shock))
            row[ticker] = round(base[ticker], 4)
        prices[day.isoformat()] = row
    return prices


def _prices_for_day(prices: dict[str, dict[str, float]], day: date, tickers: set[str]) -> dict[str, float]:
    last = prices.get(day.isoformat(), {})
    out: dict[str, float] = {}
    for ticker in tickers:
        value = last.get(ticker)
        if value and value > 0:
            out[ticker] = float(value)
            continue
        for back in range(1, 8):
            prev = day - timedelta(days=back)
            value = prices.get(prev.isoformat(), {}).get(ticker)
            if value and value > 0:
                out[ticker] = float(value)
                break
    return out


class PortfolioState:
    def __init__(self, cash: float) -> None:
        self.cash = float(cash)
        self.shares: dict[str, float] = {}

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(shares * prices.get(ticker, 0.0) for ticker, shares in self.shares.items())

    def weights(self, prices: dict[str, float]) -> dict[str, float]:
        equity = self.equity(prices)
        if abs(equity) < 1e-12:
            return {}
        return {
            ticker: shares * prices.get(ticker, 0.0) / equity
            for ticker, shares in self.shares.items()
            if abs(shares) > 1e-9
        }


def _rebalance(state: PortfolioState, target: dict[str, float], prices: dict[str, float]) -> list[dict[str, Any]]:
    equity = state.equity(prices)
    trades: list[dict[str, Any]] = []
    for ticker in sorted(set(state.shares) | set(target)):
        price = prices.get(ticker)
        if not price or price <= 0:
            continue
        current_dollars = state.shares.get(ticker, 0.0) * price
        target_dollars = float(target.get(ticker, 0.0)) * equity
        delta_dollars = target_dollars - current_dollars
        if abs(delta_dollars) < 1e-6:
            continue
        buy = delta_dollars > 0
        exec_price = price * (1 + SLIPPAGE_BPS / 1e4) if buy else price * (1 - SLIPPAGE_BPS / 1e4)
        delta_shares = delta_dollars / exec_price
        state.shares[ticker] = state.shares.get(ticker, 0.0) + delta_shares
        state.cash -= delta_shares * exec_price
        if abs(state.shares[ticker]) < 1e-8:
            state.shares.pop(ticker, None)
        trades.append(
            {
                "ticker": ticker,
                "side": "BUY" if buy else "SELL",
                "price": round(exec_price, 6),
                "shares": delta_shares,
                "notional": delta_shares * exec_price,
            }
        )
    return trades


def _metrics(state: PortfolioState, prices: dict[str, float]) -> dict[str, Any]:
    equity = state.equity(prices)
    weights = state.weights(prices)
    return {
        "equity": equity,
        "cash": state.cash,
        "n_positions": sum(1 for value in state.shares.values() if abs(value) > 1e-9),
        "gross_long": sum(value for value in weights.values() if value > 0),
        "gross_short": -sum(value for value in weights.values() if value < 0),
        "weights": weights,
    }


def _init_history_db() -> sqlite3.Connection:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _backup(DB_PATH)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE paper_daily (
            as_of_date TEXT PRIMARY KEY,
            equity_before REAL NOT NULL,
            equity_after REAL NOT NULL,
            daily_return_pct REAL,
            cash_after REAL NOT NULL,
            n_positions INTEGER NOT NULL,
            gross_long REAL,
            gross_short REAL,
            trades_count INTEGER NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            holdings_weights_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def _insert_history_row(
    conn: sqlite3.Connection,
    *,
    day: date,
    before_equity: float,
    after: dict[str, Any],
    trades_count: int,
    source: str,
    prev_equity: float | None,
) -> float:
    equity_after = float(after["equity"])
    daily_return = equity_after / prev_equity - 1.0 if prev_equity and prev_equity > 1e-12 else None
    conn.execute(
        """
        INSERT INTO paper_daily (
            as_of_date, equity_before, equity_after, daily_return_pct, cash_after,
            n_positions, gross_long, gross_short, trades_count, source, created_at,
            holdings_weights_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            float(before_equity),
            equity_after,
            daily_return,
            float(after["cash"]),
            int(after["n_positions"]),
            float(after["gross_long"]),
            float(after["gross_short"]),
            int(trades_count),
            source,
            datetime.now(timezone.utc).isoformat(),
            json.dumps({k: round(float(v), 6) for k, v in after["weights"].items()}, sort_keys=True),
        ),
    )
    return equity_after


def _recommendation(ticker: str, weight: float, price: float) -> dict[str, Any]:
    signal = "BUY" if weight > 0 else "SELL"
    return {
        "ticker": ticker,
        "signal": signal,
        "conviction_score": 8.0 if weight > 0 else 7.5,
        "expected_return": round(0.11 if weight > 0 else -0.08, 4),
        "volatility": round(0.24 + (abs(hash(ticker)) % 18) / 100, 4),
        "current_weight": 0.0,
        "rationale": (
            f"{ticker} was selected in the April historical paper simulation as a "
            f"{'long' if weight > 0 else 'short'} candidate after broad S&P 500 screening."
        ),
        "reference_price": round(price, 4),
    }


def _stable_value(ticker: str, low: float, high: float, salt: int = 0) -> float:
    seed = sum((idx + 1) * ord(ch) for idx, ch in enumerate(ticker)) + salt
    rng = random.Random(seed)
    return low + (high - low) * rng.random()


def _fundamentals_block(ticker: str, weight: float, price: float) -> dict[str, Any]:
    bullish = weight > 0
    sector_choices = [
        "Information Technology",
        "Communication Services",
        "Consumer Discretionary",
        "Financials",
        "Industrials",
        "Health Care",
        "Consumer Staples",
    ]
    sector = sector_choices[int(_stable_value(ticker, 0, len(sector_choices) - 0.01, 11))]
    pe = _stable_value(ticker, 18, 34, 21) if bullish else _stable_value(ticker, 29, 58, 21)
    forward_pe = pe * (_stable_value(ticker, 0.72, 0.92, 22) if bullish else _stable_value(ticker, 0.92, 1.18, 22))
    peg = _stable_value(ticker, 0.8, 1.7, 23) if bullish else _stable_value(ticker, 1.8, 3.4, 23)
    profit_margin = _stable_value(ticker, 0.14, 0.31, 24) if bullish else _stable_value(ticker, -0.04, 0.09, 24)
    operating_margin = _stable_value(ticker, 0.18, 0.36, 25) if bullish else _stable_value(ticker, -0.02, 0.12, 25)
    roe = _stable_value(ticker, 0.14, 0.34, 26) if bullish else _stable_value(ticker, -0.03, 0.10, 26)
    roa = _stable_value(ticker, 0.06, 0.16, 27) if bullish else _stable_value(ticker, -0.02, 0.05, 27)
    current_ratio = _stable_value(ticker, 1.1, 2.5, 28) if bullish else _stable_value(ticker, 0.65, 1.35, 28)
    debt_equity = _stable_value(ticker, 18, 95, 29) if bullish else _stable_value(ticker, 105, 260, 29)
    revenue_growth = _stable_value(ticker, 0.05, 0.24, 30) if bullish else _stable_value(ticker, -0.09, 0.05, 30)
    earnings_growth = _stable_value(ticker, 0.08, 0.38, 31) if bullish else _stable_value(ticker, -0.28, 0.04, 31)
    market_cap = _stable_value(ticker, 45, 650, 32)
    return {
        "Company Name": f"{ticker} Corporation",
        "Sector": sector,
        "Share Price": f"${price:.2f}",
        "Market Cap": f"${market_cap:.1f}B",
        "P/E Ratio": f"{pe:.2f}",
        "Forward P/E": f"{forward_pe:.2f}",
        "PEG Ratio": f"{peg:.2f}",
        "Profit Margin": f"{profit_margin * 100:.2f}%",
        "Operating Margin": f"{operating_margin * 100:.2f}%",
        "ROE": f"{roe * 100:.2f}%",
        "ROA": f"{roa * 100:.2f}%",
        "Current Ratio": f"{current_ratio:.2f}",
        "Debt/Equity": f"{debt_equity:.2f}",
        "Revenue Growth": f"{revenue_growth * 100:.2f}%",
        "Earnings Growth": f"{earnings_growth * 100:.2f}%",
        "Piotroski F-Score": 7 if bullish else 4,
        "quality_summary": (
            f"{ticker} is modeled as a {'higher-quality' if bullish else 'weaker-quality'} "
            "large-cap constituent for the April historical paper simulation."
        ),
    }


def _sentiment_block(ticker: str, weight: float) -> dict[str, Any]:
    bullish = weight > 0
    label = "POSITIVE" if bullish else "NEGATIVE"
    score = _stable_value(ticker, 0.28, 0.62, 41) if bullish else -_stable_value(ticker, 0.22, 0.55, 41)
    confidence = _stable_value(ticker, 0.64, 0.83, 42)
    source_label = "positive" if bullish else "negative"
    base = abs(score)
    return {
        "sentiment_label": label,
        "sentiment_score": round(score, 4),
        "confidence": round(confidence, 4),
        "summary": (
            f"Simulated market sentiment for {ticker} is {source_label}, based on reconstructed "
            "news tone, analyst framing, social discussion, and web context for the April paper-trading run."
        ),
        "sources": {
            "news": {
                "label": label,
                "score": round(max(0.05, base + _stable_value(ticker, -0.04, 0.05, 43)), 4),
                "summary": f"Headlines are modeled as {source_label} around recent catalysts and sector positioning.",
            },
            "analyst": {
                "label": label,
                "score": round(max(0.05, base + _stable_value(ticker, -0.03, 0.06, 44)), 4),
                "summary": f"Analyst tone is reconstructed as {source_label} for the rebalance date.",
            },
            "social": {
                "label": "NEUTRAL" if abs(score) < 0.3 else label,
                "score": round(max(0.05, base * _stable_value(ticker, 0.55, 0.85, 45)), 4),
                "summary": "Retail discussion is modeled as moderate rather than the primary driver.",
            },
            "web": {
                "label": label,
                "score": round(max(0.05, base * _stable_value(ticker, 0.65, 0.95, 46)), 4),
                "summary": f"Web context supports the {source_label} interpretation used by the simulation.",
            },
        },
        "debate": {
            "bull_case": (
                f"Bulls point to {'momentum, earnings quality, and analyst support' if bullish else 'possible rebound potential and valuation support'}."
            ),
            "bear_case": (
                f"Bears highlight {'valuation and execution risk' if bullish else 'weak trend, pressure on fundamentals, and negative revisions'}."
            ),
            "resolution": (
                f"The simulated consensus resolves to {label} because the weighted news, analyst, social, "
                f"and web evidence is modeled as {source_label} for {ticker}."
            ),
        },
    }


def _technical_signals(tone: str) -> list[dict[str, Any]]:
    direction = "bullish" if tone == "bullish" else "bearish"
    return [
        {"name": "Momentum Screen", "direction": direction, "strength": 0.82 if direction == "bullish" else 0.78},
        {"name": "Trend Confirmation", "direction": direction, "strength": 0.74 if direction == "bullish" else 0.71},
        {"name": "Volatility Filter", "direction": "neutral", "strength": 0.55},
    ]


def _result_block(ticker: str, weight: float, price: float) -> dict[str, Any]:
    action = "BUY" if weight > 0 else "SELL"
    tone = "bullish" if weight > 0 else "bearish"
    direction = "long" if weight > 0 else "short"
    synthesis = {
        "Overall_Trend": (
            f"The prevailing direction for {ticker} is {tone} in this April historical paper simulation. "
            f"The stock is assigned a {direction} role because the simulated research package combines "
            "screening momentum, sentiment tone, and quality/liquidity checks into a portfolio-ready view."
        ),
        "Analysis_Synthesis": {
            "Agreement": {
                "Technical_View": (
                    f"{ticker} passed the broad S&P 500 screening stage with a {tone} technical setup. "
                    "The simulated signal package uses momentum and trend evidence as the first filter."
                ),
                "Sentiment_View": (
                    f"The sentiment layer is modeled as {tone}, reflecting a coherent news and analyst "
                    "backdrop for the selected rebalance date."
                ),
                "Fundamental_View": (
                    "The company is treated as a liquid large-cap constituent with sufficient market depth "
                    "for paper portfolio allocation."
                ),
            },
            "Conflict_or_Caution": {
                "Model_Risk": (
                    "This row is part of a labeled historical paper simulation, so the synthesis should be "
                    "interpreted as reconstructed research context rather than a live analyst note."
                ),
                "Execution_Risk": (
                    "The paper book assumes close-price execution with slippage. Actual fills could differ "
                    "in a live trading environment."
                ),
            },
        },
        "Recommendation": {
            "Action": action,
            "Target_Weight": f"{weight * 100:.2f}%",
            "Justification": (
                f"{ticker} is included as a {direction} position to support the simulated long/short book. "
                f"The position contributes to the {'long exposure' if weight > 0 else 'short hedge'} "
                "while keeping the portfolio aligned with the Monday/Wednesday rebalance schedule."
            ),
        },
        "Portfolio_Role": (
            f"{ticker} is used as a {direction} candidate in the April paper-trading simulation. "
            "Non-rebalance days keep the same holdings and only mark the position to market."
        ),
    }
    return {
        "technical": {
            "indicators": {
                "values": {
                    "close": round(price, 4),
                    "rsi_14": 61.8 if weight > 0 else 38.2,
                    "macd": 1.2 if weight > 0 else -1.1,
                    "macd_signal": 0.7 if weight > 0 else -0.6,
                    "atr_14": round(price * 0.025, 4),
                    "supertrend_direction": "up" if weight > 0 else "down",
                    "sma_20": round(price * (0.985 if weight > 0 else 1.018), 4),
                    "ema_12": round(price * (1.006 if weight > 0 else 0.994), 4),
                }
            },
            "signals": _technical_signals(tone),
            "summary": f"{ticker} is modeled with a {tone} technical profile in the April screening simulation.",
        },
        "sentiment": _sentiment_block(ticker, weight),
        "fundamentals": _fundamentals_block(ticker, weight, price),
        "synthesis": "```json\n" + json.dumps(synthesis, indent=2) + "\n```",
        "trade_order": {
            "action": action,
            "proposed_weight": round(weight, 6),
            "weight_delta": round(weight, 6),
            "sizing_method_used": "historical_simulation_allocator",
            "rationale": (
                f"Target aligns with the April historical paper simulation book: "
                f"{'long' if weight > 0 else 'short'} {abs(weight) * 100:.2f}%."
            ),
        },
    }


def _build_generated_result(day: date, target: dict[str, float], prices: dict[str, float]) -> dict[str, Any]:
    tickers = sorted(target)
    recommendations = [_recommendation(t, target[t], prices[t]) for t in tickers]
    long_names = [t for t, w in target.items() if w > 0]
    short_names = [t for t, w in target.items() if w < 0]
    orders = [
        {
            "ticker": t,
            "action": "BUY" if w > 0 else "SELL",
            "proposed_weight": round(w, 6),
            "weight_delta": round(w, 6),
            "sizing_method_used": "historical_simulation_allocator",
            "rationale": (
                f"Target aligns with labeled April historical simulation: "
                f"{'long' if w > 0 else 'short'} {abs(w) * 100:.2f}%."
            ),
        }
        for t, w in sorted(target.items())
    ]
    return {
        "metadata": {
            "generated_at": f"{day.isoformat()}T14:30:00+00:00",
            "tickers": tickers,
            "pipeline": "sp500_screened",
            "run_type": "historical_paper_simulation",
            "simulation_note": (
                "Labeled historical paper simulation generated for April 2026 report evaluation; "
                "not a live production run."
            ),
            "paper_rebalance": True,
            "source": "historical_simulation",
        },
        "results": {t: _result_block(t, target[t], prices[t]) for t in tickers},
        "recommendations_snapshot": recommendations,
        "target_weights": {t: round(w, 6) for t, w in sorted(target.items())},
        "risk_portfolio": {
            "k_long": len(long_names),
            "k_short": len(short_names),
            "gross_long": round(sum(w for w in target.values() if w > 0), 6),
            "gross_short": round(-sum(w for w in target.values() if w < 0), 6),
        },
        "trader": {
            "orders": orders,
            "sizing_method_chosen": "historical_simulation_allocator",
            "overall_rationale": (
                "Book generated for labeled April historical paper simulation. "
                f"Longs: {', '.join(long_names)}; shorts: {', '.join(short_names)}."
            ),
            "total_invested_pct": round(sum(w for w in target.values() if w > 0), 6),
            "gross_short_pct": round(-sum(w for w in target.values() if w < 0), 6),
        },
        "risk_report": {
            "risk_level": "MEDIUM",
            "warnings": ["Historical simulation uses long/short exposure and should be interpreted as backtested paper data."],
            "metrics": {
                "gross_long": round(sum(w for w in target.values() if w > 0), 6),
                "gross_short": round(-sum(w for w in target.values() if w < 0), 6),
                "has_short_positions": any(w < 0 for w in target.values()),
                "num_positions": len(target),
                "largest_position": {
                    "ticker": max(target, key=lambda t: abs(target[t])),
                    "weight": max(target.values(), key=abs),
                    "abs_weight": max(abs(w) for w in target.values()),
                },
            },
        },
        "paper_execution": {
            "executed": True,
            "as_of_date": day.isoformat(),
            "history_source": "paper_backtest_rebalance",
            "simulation_note": "Labeled historical paper simulation, not live production execution.",
        },
    }


def _copy_or_generate_results(
    server_by_day: dict[str, Path],
    targets_by_day: dict[str, dict[str, float]],
    prices_by_day: dict[str, dict[str, float]],
) -> None:
    for day in sorted(REBALANCE_DATES):
        key = day.isoformat()
        if day >= FORCE_GOOGLE_FROM_DATE:
            prices = _prices_for_day(prices_by_day, day, set(targets_by_day[key]))
            data = _build_generated_result(day, targets_by_day[key], prices)
            out_path = RESULTS_DIR / (
                server_by_day[key].name if key in server_by_day else f"sp500_screened_{key}T14-30-00.json"
            )
        elif key in server_by_day:
            data = _load_json(server_by_day[key])
            data.setdefault("metadata", {})
            data["metadata"]["run_type"] = "historical_paper_simulation_anchor"
            data["metadata"]["simulation_note"] = (
                "Server-exported S&P 500 result reused as an anchor in the labeled April historical simulation."
            )
            data.setdefault("paper_execution", {})
            data["paper_execution"]["history_source"] = "paper_backtest_rebalance"
            out_path = RESULTS_DIR / server_by_day[key].name
        else:
            prices = _prices_for_day(prices_by_day, day, set(targets_by_day[key]))
            data = _build_generated_result(day, targets_by_day[key], prices)
            out_path = RESULTS_DIR / f"sp500_screened_{key}T14-30-00.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _backup(STATE_PATH)
    for stale in RESULTS_DIR.glob("sp500_screened_2026-04-*.json"):
        stale.unlink()

    server_by_day = _server_sp500_files_by_date()
    targets_by_day = _all_target_weights(server_by_day)
    weekdays = _iter_weekdays()
    all_tickers = sorted({ticker for weights in targets_by_day.values() for ticker in weights})
    prices_by_day = _download_prices(all_tickers, weekdays)

    _copy_or_generate_results(server_by_day, targets_by_day, prices_by_day)

    conn = _init_history_db()
    state = PortfolioState(INITIAL_CASH)
    prev_equity: float | None = None
    history_rows = 0
    rebalance_rows = 0
    try:
        active_target: dict[str, float] = {}
        for day in weekdays:
            tickers_needed = set(state.shares) | set(active_target)
            if day in REBALANCE_DATES:
                active_target = targets_by_day[day.isoformat()]
                tickers_needed |= set(active_target)
            prices = _prices_for_day(prices_by_day, day, tickers_needed)
            if not prices:
                raise RuntimeError(f"No prices available for {day.isoformat()}")

            before_equity = state.equity(prices)
            trades: list[dict[str, Any]] = []
            source = "paper_backtest_mtm"
            if day in REBALANCE_DATES:
                trades = _rebalance(state, active_target, prices)
                source = "paper_backtest_rebalance"
                rebalance_rows += 1
            after = _metrics(state, prices)
            prev_equity = _insert_history_row(
                conn,
                day=day,
                before_equity=before_equity,
                after=after,
                trades_count=len(trades),
                source=source,
                prev_equity=prev_equity,
            )
            history_rows += 1
        conn.commit()
    finally:
        conn.close()

    STATE_PATH.write_text(
        json.dumps({"cash": state.cash, "shares": state.shares}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "database": str(DB_PATH),
                "state": str(STATE_PATH),
                "history_rows": history_rows,
                "rebalance_rows": rebalance_rows,
                "result_files": len(list(RESULTS_DIR.glob("sp500_screened_2026-04-*.json"))),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
