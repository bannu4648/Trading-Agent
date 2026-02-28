"""
Fundamentals Agent - Main entry point.
Run:  python main.py AAPL   or   python main.py
"""
import sys
import os
from datetime import date

# Ensure package root is on path when run as script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_builder import build_canonical_report, save_canonical_report


def main():
    if len(sys.argv) > 1:
        ticker = sys.argv[1].strip().upper()
    else:
        ticker = input("Ticker symbol: ").strip().upper()
    if not ticker:
        print("No ticker provided.")
        sys.exit(1)

    trade_date = date.today().strftime("%Y-%m-%d")
    try_av = bool(os.environ.get("ALPHA_VANTAGE_API_KEY"))

    print(f"Building report for {ticker} ({trade_date})...")
    report = build_canonical_report(ticker, trade_date, try_alpha_vantage=try_av)
    print()
    print(report)

    save_choice = input("\nSave to reports folder? (Y/N) [Y]: ").strip().upper()
    if save_choice != "N":
        path = save_canonical_report(ticker, trade_date, try_alpha_vantage=try_av)
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
