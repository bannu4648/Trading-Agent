"""
Compare top-10 fundamentals reports: structure and data completeness.
"""
import os
import sys
from datetime import date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

REQUIRED_SECTIONS = [
    "Company Overview",
    "Key Financial Metrics",
    "Balance Sheet Summary",
    "Income Statement Summary",
    "Cash Flow Summary",
    "Growth and Valuation",
    "Summary Table",
]

# Data points we expect to see in a complete report (substrings or regex)
EXPECTED_DATA = [
    ("Share Price", "Share Price", "share price"),
    ("Data retrieved", "Data retrieved", "data retrieved"),
    ("Market Cap", "Market Cap", "market cap"),
    ("P/E", "P/E", "p/e"),
    ("Revenue", "Revenue", "revenue"),
    ("Net Income", "Net Income", "net income"),
    ("Total Assets", "Total Assets", "total assets"),
    ("Operating", "Operating", "operating"),  # cash flow
]

TOP_10_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "AVGO", "TSLA",
]


def safe_ticker_for_file(ticker: str) -> str:
    return ticker.replace(".", "_")


def check_report(path: str) -> dict:
    if not os.path.isfile(path):
        return {"ok": False, "missing_sections": ["File not found"], "missing_data": [], "path": path, "length": 0}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    missing_sections = [s for s in REQUIRED_SECTIONS if s not in content]
    missing_data = []
    content_lower = content.lower()
    for name, *patterns in EXPECTED_DATA:
        if not any(p.lower() in content_lower or p in content for p in patterns):
            missing_data.append(name)
    return {
        "ok": len(missing_sections) == 0 and len(missing_data) == 0,
        "missing_sections": missing_sections,
        "missing_data": missing_data,
        "path": path,
        "length": len(content),
    }


def main():
    reports_dir = os.path.join(_PROJECT_ROOT, "reports")
    if not os.path.isdir(reports_dir):
        print("No reports directory found. Run run_batch_top10.py first.")
        return
    trade_date = date.today().strftime("%Y-%m-%d")
    print("Required sections:", ", ".join(REQUIRED_SECTIONS))
    print("Expected data:", ", ".join([e[0] for e in EXPECTED_DATA]))
    print("-" * 70)
    all_ok = True
    results = []
    for t in TOP_10_TICKERS:
        safe = safe_ticker_for_file(t)
        path = os.path.join(reports_dir, f"fundamentals_report_{safe}_{trade_date}.md")
        r = check_report(path)
        results.append((t, r))
        sec_status = "OK" if not r["missing_sections"] else "MISSING: " + ", ".join(r["missing_sections"])
        data_status = "OK" if not r["missing_data"] else "MISSING: " + ", ".join(r["missing_data"])
        if not r["ok"]:
            all_ok = False
        print(f"  {t:6}  sections: {sec_status}")
        if r["missing_data"]:
            print(f"          data:   {data_status}")
        print(f"          size:   {r.get('length', 0)} chars")
    print("-" * 70)
    if all_ok:
        print("All reports present with required sections and expected data.")
    else:
        missing_per_ticker = [(t, r["missing_sections"], r["missing_data"]) for t, r in results if not r["ok"]]
        print("Summary of issues:")
        for t, sec, data in missing_per_ticker:
            if sec or data:
                print(f"  {t}: sections {sec or 'ok'}, data {data or 'ok'}")


if __name__ == "__main__":
    main()
