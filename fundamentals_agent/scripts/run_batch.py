"""
Run fundamentals agent for multiple tickers (AAPL, NVDA, MSFT) and save reports.
No interactive prompts. Use for consistent comparison.
"""
import sys
import os
from datetime import date, datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from agent import FundamentalsAgent
from config import get_llm_client, DEFAULT_CONFIG


def run_one(ticker: str, trade_date: str, agent: FundamentalsAgent, out_dir: str = "reports") -> str:
    """Run agent for one ticker; save .md report. Returns path to saved file."""
    data_retrieved_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    state = agent.analyze(ticker=ticker, trade_date=trade_date)
    report = agent.get_report(state)
    if not report:
        return ""
    os.makedirs(out_dir, exist_ok=True)
    safe = ticker.replace(" ", "_")
    path = os.path.join(out_dir, f"fundamentals_report_{safe}_{trade_date}.md")
    report_generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Fundamentals Analysis Report\n\n")
        f.write(f"| Field | Value |\n|-------|--------|\n")
        f.write(f"| **Ticker** | {ticker} |\n| **Report Date** | {trade_date} |\n")
        f.write(f"| **Report generated** | {report_generated} |\n| **Data retrieved at** | {data_retrieved_at} |\n\n---\n\n")
        f.write(report)
    return path


def main():
    tickers = ["AAPL", "NVDA", "MSFT"]
    trade_date = date.today().strftime("%Y-%m-%d")

    print("Configuring agent (Ollama, max_iterations=6 for full data)...")
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "ollama"
    config["model"] = "llama3.2"
    config["debug"] = False
    config["max_iterations"] = 6

    llm = get_llm_client(config)
    agent = FundamentalsAgent(
        llm=llm,
        max_iterations=config["max_iterations"],
        vendor="yfinance",
        debug=False,
    )

    paths = []
    for t in tickers:
        print(f"Running {t}...")
        path = run_one(t, trade_date, agent)
        if path:
            print(f"  Saved: {path}")
            paths.append(path)
        else:
            print(f"  No report for {t}")

    print("\nDone. Reports:", paths)
    return paths


if __name__ == "__main__":
    main()
