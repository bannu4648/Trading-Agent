"""
Build a canonical fundamentals report with identical structure and metrics for every ticker.
Uses structured data fetchers (yfinance + Alpha Vantage fallback). Summary/analysis can be added separately.
"""
import os
from datetime import datetime, timezone

from report_schema import (
    COMPANY_OVERVIEW_FIELDS,
    KEY_METRICS_FIELDS,
    BALANCE_SHEET_FIELDS,
    INCOME_STATEMENT_FIELDS,
    CASH_FLOW_FIELDS,
    GROWTH_FIELDS,
    SUMMARY_TABLE_FIELDS,
)
from tools import (
    fetch_fundamentals_data,
    fetch_balance_sheet_data,
    fetch_cashflow_data,
    fetch_income_statement_data,
)


def _table_from_dict(d: dict, keys: list, header_name: str = "Metric") -> str:
    """Produce a markdown table with fixed row order; value or N/A."""
    rows = [f"| {header_name} | Value |", "| --- | --- |"]
    for k in keys:
        v = d.get(k, "N/A")
        if v is None or (isinstance(v, float) and str(v) == "nan"):
            v = "N/A"
        rows.append(f"| {k} | {v} |")
    return "\n".join(rows)


def build_canonical_report(ticker: str, trade_date: str, try_alpha_vantage: bool = True) -> str:
    """
    Build a report with identical sections and metrics for every ticker.
    Uses N/A for any missing data. Tries yfinance first, then Alpha Vantage for statements if empty.
    """
    fundamentals = fetch_fundamentals_data(ticker, try_alpha_vantage=try_alpha_vantage)
    balance_sheet = fetch_balance_sheet_data(ticker, freq="quarterly", try_alpha_vantage=try_alpha_vantage)
    income_stmt = fetch_income_statement_data(ticker, freq="quarterly", try_alpha_vantage=try_alpha_vantage)
    cash_flow = fetch_cashflow_data(ticker, freq="quarterly", try_alpha_vantage=try_alpha_vantage)

    sections = []

    # 1. Company Overview
    sections.append("### Company Overview\n")
    sections.append(_table_from_dict(fundamentals, COMPANY_OVERVIEW_FIELDS, "Field"))

    # 2. Key Financial Metrics
    sections.append("\n### Key Financial Metrics\n")
    sections.append(_table_from_dict(fundamentals, KEY_METRICS_FIELDS, "Metric"))

    # 3. Balance Sheet Summary
    sections.append("\n### Balance Sheet Summary\n")
    sections.append(_table_from_dict(balance_sheet, BALANCE_SHEET_FIELDS, "Line Item"))

    # 4. Income Statement Summary
    sections.append("\n### Income Statement Summary\n")
    sections.append(_table_from_dict(income_stmt, INCOME_STATEMENT_FIELDS, "Line Item"))

    # 5. Cash Flow Summary
    sections.append("\n### Cash Flow Summary\n")
    sections.append(_table_from_dict(cash_flow, CASH_FLOW_FIELDS, "Line Item"))

    # 6. Growth and Valuation
    sections.append("\n### Growth and Valuation\n")
    sections.append(_table_from_dict(fundamentals, GROWTH_FIELDS, "Metric"))

    # 7. Summary Table (same metrics for every report)
    summary_dict = {k: fundamentals.get(k, "N/A") for k in SUMMARY_TABLE_FIELDS}
    sections.append("\n### Summary Table\n")
    sections.append(_table_from_dict(summary_dict, SUMMARY_TABLE_FIELDS, "Metric"))

    return "\n".join(sections)


def save_canonical_report(
    ticker: str,
    trade_date: str,
    out_dir: str = "reports",
    try_alpha_vantage: bool = True,
) -> str:
    """Build canonical report and save to reports/<file>.md. Returns path to file."""
    os.makedirs(out_dir, exist_ok=True)
    report_body = build_canonical_report(ticker, trade_date, try_alpha_vantage)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    safe_ticker = ticker.replace(" ", "_").replace(".", "_")
    path = os.path.join(out_dir, f"fundamentals_report_{safe_ticker}_{trade_date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Fundamentals Analysis Report\n\n")
        f.write("| Field | Value |\n|-------|--------|\n")
        f.write(f"| **Ticker** | {ticker} |\n| **Report Date** | {trade_date} |\n")
        f.write(f"| **Report generated** | {now} |\n| **Data retrieved at** | {now} |\n\n---\n\n")
        f.write(report_body)
    return path
