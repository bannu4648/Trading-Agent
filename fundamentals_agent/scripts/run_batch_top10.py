"""
Run fundamentals report for the top 10 US companies by market cap.
Uses canonical report builder (identical structure and metrics; no LLM required).
Optional: set USE_AGENT=1 to use the LLM agent instead.
"""
import sys
import os
from datetime import date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

# Top 10 US companies by market cap (typical 2025 order; tickers for yfinance)
TOP_10_TICKERS = [
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # NVIDIA
    "GOOGL",  # Alphabet (Google)
    "AMZN",   # Amazon
    "META",   # Meta
    "BRK-B",  # Berkshire Hathaway (yfinance uses BRK-B)
    "LLY",    # Eli Lilly
    "AVGO",   # Broadcom
    "TSLA",   # Tesla
]


def run_one_canonical(ticker: str, trade_date: str, out_dir: str = "reports", try_av: bool = True) -> str:
    """Build and save canonical report (identical metrics). Returns path."""
    from report_builder import save_canonical_report
    return save_canonical_report(ticker, trade_date, out_dir=out_dir, try_alpha_vantage=try_av)


def run_one_agent(ticker: str, trade_date: str, agent, out_dir: str = "reports") -> str:
    """Run LLM agent and save report. Returns path."""
    from datetime import datetime, timezone
    data_retrieved_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    state = agent.analyze(ticker=ticker, trade_date=trade_date)
    report = agent.get_report(state)
    if not report:
        return ""
    os.makedirs(out_dir, exist_ok=True)
    safe = ticker.replace(" ", "_").replace(".", "_")
    path = os.path.join(out_dir, f"fundamentals_report_{safe}_{trade_date}.md")
    report_generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Fundamentals Analysis Report\n\n")
        f.write("| Field | Value |\n|-------|--------|\n")
        f.write(f"| **Ticker** | {ticker} |\n| **Report Date** | {trade_date} |\n")
        f.write(f"| **Report generated** | {report_generated} |\n| **Data retrieved at** | {data_retrieved_at} |\n\n---\n\n")
        f.write(report)
    return path


def main():
    tickers = TOP_10_TICKERS
    trade_date = date.today().strftime("%Y-%m-%d")
    use_agent = os.environ.get("USE_AGENT", "").strip() in ("1", "true", "yes")

    print("Top 10 US by market cap:", ", ".join(tickers))
    try_av = bool(os.environ.get("ALPHA_VANTAGE_API_KEY"))

    if use_agent:
        print("Using LLM agent (USE_AGENT=1)...")
        from agent import FundamentalsAgent
        from config import get_llm_client, DEFAULT_CONFIG
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "ollama"
        config["model"] = "llama3.2"
        config["debug"] = False
        config["max_iterations"] = 6
        llm = get_llm_client(config)
        agent = FundamentalsAgent(llm=llm, max_iterations=6, vendor="yfinance", debug=False)
        run_one = lambda t: run_one_agent(t, trade_date, agent)
    else:
        print("Using canonical report builder (identical structure & metrics; no LLM).")
        if try_av:
            print("Alpha Vantage key set: will use as fallback for missing data.")
        run_one = lambda t: run_one_canonical(t, trade_date, try_av=try_av)

    paths = []
    for i, t in enumerate(tickers, 1):
        print(f"[{i}/10] {t}...")
        try:
            path = run_one(t)
            if path:
                print(f"       Saved: {path}")
                paths.append(path)
            else:
                print(f"       No report for {t}")
        except Exception as e:
            print(f"       Error: {e}")
            import traceback
            traceback.print_exc()

    print("\nDone. Run compare_reports_top10.py to check completeness.")
    return paths


if __name__ == "__main__":
    main()
