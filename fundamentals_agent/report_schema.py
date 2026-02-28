"""
Canonical report schema: exact metrics and order for identical reports across all tickers.
Every report must include every row; use N/A when data is missing.
"""

# Company Overview - exact fields in order
COMPANY_OVERVIEW_FIELDS = [
    "Company Name",
    "Sector",
    "Industry",
    "Share Price",
    "Market Cap",
    "Enterprise Value",
    "Data retrieved at",
]

# Key Financial Metrics - exact rows in order (all reports show all rows; N/A if missing)
KEY_METRICS_FIELDS = [
    "P/E Ratio",
    "Forward P/E",
    "PEG Ratio",
    "Price/Book",
    "Price/Sales",
    "EV/Revenue",
    "EV/EBITDA",
    "Profit Margin",
    "Operating Margin",
    "ROE",
    "ROA",
    "Current Ratio",
    "Quick Ratio",
    "Debt/Equity",
    "Cash per Share",
    "Book Value",
]

# Balance Sheet - standard line items (most recent period)
BALANCE_SHEET_FIELDS = [
    "Total Assets",
    "Total Liabilities",
    "Total Equity",
    "Cash And Cash Equivalents",
    "Accounts Receivable",
    "Inventory",
    "Total Current Assets",
]

# Income Statement - standard line items
INCOME_STATEMENT_FIELDS = [
    "Total Revenue",
    "Cost Of Revenue",
    "Gross Profit",
    "Operating Income",
    "Net Income",
]

# Cash Flow - standard line items
CASH_FLOW_FIELDS = [
    "Operating Cash Flow",
    "Investing Cash Flow",
    "Financing Cash Flow",
    "Net Change In Cash",
]

# Growth and Valuation - standard fields
GROWTH_FIELDS = [
    "Revenue Growth",
    "Earnings Growth",
]

# Summary table - same metrics for every report
SUMMARY_TABLE_FIELDS = [
    "Market Cap",
    "Enterprise Value",
    "Share Price",
    "P/E Ratio",
    "PEG Ratio",
    "Profit Margin",
    "ROE",
    "Current Ratio",
    "Revenue Growth",
]
