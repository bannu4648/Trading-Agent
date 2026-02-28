"""
Trader Agent — standalone entry point for testing.

Usage:
    python -m trader_agent.main

Loads .env from the Trading-Agent project root automatically.
Requires GROQ_API_KEY to be set there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (Trading-Agent/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _check_env() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY is not set.")
        print("Add it to Trading-Agent/.env:  GROQ_API_KEY=gsk_...")
        sys.exit(1)


def _print_banner(title: str) -> None:
    width = 70
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _print_section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def main() -> None:
    _check_env()

    from .agent import run_trader_agent
    from .mock_inputs import MOCK_RESEARCH_OUTPUT

    _print_banner("TRADER AGENT — Standalone Test Run")

    print(f"\n  Cash in portfolio : {MOCK_RESEARCH_OUTPUT.portfolio_cash_pct:.0%}")
    print(f"  Stocks analysed   : {len(MOCK_RESEARCH_OUTPUT.recommendations)}")
    print()

    header = f"  {'Ticker':<8} {'Signal':<6} {'Score':>5}  {'ExpRet':>7}  {'Vol':>6}  {'CurrWt':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for rec in MOCK_RESEARCH_OUTPUT.recommendations:
        print(
            f"  {rec.ticker:<8} {rec.signal:<6} {rec.conviction_score:>5.1f}"
            f"  {rec.expected_return:>+6.0%}  {rec.volatility:>5.0%}  {rec.current_weight:>6.0%}"
        )

    _print_section("Running Trader Agent...")

    result = run_trader_agent(MOCK_RESEARCH_OUTPUT)

    _print_banner("TRADER AGENT OUTPUT")
    print(f"\n  Sizing method : {result.sizing_method_chosen}")
    print(f"  Total invested: {result.total_invested_pct:.1%}")
    print(f"\n  Rationale:\n")
    for line in result.overall_rationale.split(". "):
        if line.strip():
            print(f"    {line.strip()}.")

    _print_section("Trade Orders")
    for order in result.orders:
        print(
            f"  {order.ticker:<8} {order.action:<6} {order.proposed_weight:>6.1%}"
            f"  {order.weight_delta:>+7.1%}  {order.sizing_method_used}"
        )
        print(f"           {order.rationale}")
        print()

    _print_banner("END")


if __name__ == "__main__":
    main()
