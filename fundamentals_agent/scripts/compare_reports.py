"""
Check that saved fundamentals reports have a uniform structure and no missing sections.
"""
import os
import sys

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


def check_report(path: str) -> dict:
    """Return {'ok': bool, 'missing': [...], 'has_table': bool per section}."""
    if not os.path.isfile(path):
        return {"ok": False, "missing": ["File not found"], "path": path}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    missing = []
    for sec in REQUIRED_SECTIONS:
        if sec not in content:
            missing.append(sec)
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "path": path,
        "length": len(content),
    }


def main():
    reports_dir = os.path.join(_PROJECT_ROOT, "reports")
    if not os.path.isdir(reports_dir):
        print("No reports directory found.")
        return
    tickers = ["AAPL", "NVDA", "MSFT"]
    from datetime import date
    trade_date = date.today().strftime("%Y-%m-%d")
    print("Report structure check (required sections: {})".format(", ".join(REQUIRED_SECTIONS)))
    print("-" * 60)
    all_ok = True
    for t in tickers:
        path = os.path.join(reports_dir, f"fundamentals_report_{t}_{trade_date}.md")
        r = check_report(path)
        status = "OK" if r["ok"] else "MISSING: " + ", ".join(r["missing"])
        print(f"  {t}: {status}  ({r.get('length', 0)} chars)")
        if not r["ok"]:
            all_ok = False
    print("-" * 60)
    print("All reports uniform." if all_ok else "Some reports missing sections; re-run agent with updated prompt.")


if __name__ == "__main__":
    main()
