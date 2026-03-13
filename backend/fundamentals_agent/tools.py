"""
Fundamental data tools for the Fundamentals Agent.
Supports multiple data vendors (yfinance, Alpha Vantage).
"""
import os
import pandas as pd
from datetime import datetime, timezone
from typing import Annotated
from langchain_core.tools import tool
import yfinance as yf
import requests
import json


def _format_financial_value(val) -> str:
    """Format a single financial value for readable output (no scientific notation)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    if isinstance(val, (int, float)):
        if abs(val) >= 1e12:
            return f"{val/1e12:.2f}T"
        if abs(val) >= 1e9:
            return f"{val/1e9:.2f}B"
        if abs(val) >= 1e6:
            return f"{val/1e6:.2f}M"
        if abs(val) >= 1e3:
            return f"{val/1e3:.2f}K"
        if isinstance(val, float) and val != int(val):
            return f"{val:.2f}"
        return str(int(val))
    return str(val)


def _format_df_for_report(df: pd.DataFrame, max_cols: int = 5) -> str:
    """Format a DataFrame for report: readable numbers, no NaN, limit columns for readability."""
    if df.empty:
        return "(No data)"
    df = df.copy()
    # Take most recent columns only
    if len(df.columns) > max_cols:
        df = df.iloc[:, :max_cols]
    # Format values
    for col in df.columns:
        df[col] = df[col].apply(_format_financial_value)
    df.index = [str(i).replace("_", " ").title() for i in df.index]
    return df.to_string()


def _get_alpha_vantage_api_key() -> str:
    """Get Alpha Vantage API key from environment."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is not set.")
    return api_key


def _make_alpha_vantage_request(function_name: str, symbol: str) -> str:
    """Make a request to Alpha Vantage API."""
    api_key = _get_alpha_vantage_api_key()
    url = "https://www.alphavantage.co/query"
    params = {
        "function": function_name,
        "symbol": symbol,
        "apikey": api_key,
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    # Check for API errors
    if "Error Message" in data:
        raise ValueError(f"Alpha Vantage API Error: {data['Error Message']}")
    if "Information" in data:
        info = data["Information"]
        if "rate limit" in info.lower():
            raise ValueError(f"Alpha Vantage rate limit exceeded: {info}")
    
    return json.dumps(data, indent=2)


@tool
def get_fundamentals(
    ticker: Annotated[str, "Stock ticker symbol (e.g., 'AAPL', 'NVDA')"],
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"],
    vendor: Annotated[str, "Data vendor: 'yfinance' or 'alpha_vantage'"] = "yfinance",
) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol.
    
    This includes company overview, key metrics, financial ratios, and company profile.
    
    Args:
        ticker: Stock ticker symbol
        curr_date: Current date (used for context, not filtering)
        vendor: Data vendor to use ('yfinance' or 'alpha_vantage')
    
    Returns:
        Formatted string containing comprehensive fundamental data
    """
    try:
        if vendor == "alpha_vantage":
            return _make_alpha_vantage_request("OVERVIEW", ticker)
        else:
            # Use yfinance
            stock = yf.Ticker(ticker)
            info = stock.info
            retrieved_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            # Share price: current or last close
            share_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if share_price is None or (isinstance(share_price, float) and (pd.isna(share_price) or share_price <= 0)):
                share_price_str = "N/A"
            else:
                share_price_str = f"${float(share_price):,.2f}"

            # Format key fundamental metrics
            report = f"=== Company Overview: {ticker} ===\n\n"
            report += f"Company Name: {info.get('longName', 'N/A')}\n"
            report += f"Sector: {info.get('sector', 'N/A')}\n"
            report += f"Industry: {info.get('industry', 'N/A')}\n"
            report += f"Share Price: {share_price_str}\n"
            report += f"Market Cap: ${info.get('marketCap', 0):,.0f}\n"
            report += f"Enterprise Value: ${info.get('enterpriseValue', 0):,.0f}\n"
            report += f"Data retrieved at: {retrieved_at}\n\n"

            report += "=== Key Financial Metrics ===\n"
            report += f"P/E Ratio: {info.get('trailingPE', 'N/A')}\n"
            report += f"Forward P/E: {info.get('forwardPE', 'N/A')}\n"
            report += f"PEG Ratio: {info.get('pegRatio', 'N/A')}\n"
            report += f"Price/Book: {info.get('priceToBook', 'N/A')}\n"
            report += f"Price/Sales: {info.get('priceToSalesTrailing12Months', 'N/A')}\n"
            report += f"EV/Revenue: {info.get('enterpriseToRevenue', 'N/A')}\n"
            report += f"EV/EBITDA: {info.get('enterpriseToEbitda', 'N/A')}\n\n"
            
            def _pct(val):
                if val is None or (isinstance(val, float) and (pd.isna(val) or val == 0)):
                    return "N/A"
                return f"{float(val)*100:.2f}%"
            report += "=== Profitability ===\n"
            report += f"Profit Margin: {_pct(info.get('profitMargins'))}\n"
            report += f"Operating Margin: {_pct(info.get('operatingMargins'))}\n"
            report += f"ROE: {_pct(info.get('returnOnEquity'))}\n"
            report += f"ROA: {_pct(info.get('returnOnAssets'))}\n\n"
            report += "=== Growth Metrics ===\n"
            report += f"Revenue Growth: {_pct(info.get('revenueGrowth'))}\n"
            report += f"Earnings Growth: {_pct(info.get('earningsGrowth'))}\n"
            report += f"Quarterly Revenue Growth: {_pct(info.get('quarterlyRevenueGrowth'))}\n"
            report += f"Quarterly Earnings Growth: {_pct(info.get('quarterlyEarningsGrowth'))}\n\n"
            
            report += "=== Financial Health ===\n"
            report += f"Current Ratio: {info.get('currentRatio', 'N/A')}\n"
            report += f"Quick Ratio: {info.get('quickRatio', 'N/A')}\n"
            report += f"Debt/Equity: {info.get('debtToEquity', 'N/A')}\n"
            report += f"Cash per Share: ${info.get('totalCashPerShare', 'N/A')}\n"
            report += f"Book Value: ${info.get('bookValue', 'N/A')}\n"
            
            return report
    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


@tool
def get_balance_sheet(
    ticker: Annotated[str, "Stock ticker symbol"],
    freq: Annotated[str, "Reporting frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"] = None,
    vendor: Annotated[str, "Data vendor: 'yfinance' or 'alpha_vantage'"] = "yfinance",
) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol.
    
    Args:
        ticker: Stock ticker symbol
        freq: Reporting frequency ('annual' or 'quarterly')
        curr_date: Current date (optional, for context)
        vendor: Data vendor to use
    
    Returns:
        Formatted string containing balance sheet data
    """
    try:
        if vendor == "alpha_vantage":
            return _make_alpha_vantage_request("BALANCE_SHEET", ticker)
        else:
            # Use yfinance
            stock = yf.Ticker(ticker)
            if freq == "annual":
                bs = stock.balance_sheet
            else:
                bs = stock.quarterly_balance_sheet
            
            if bs.empty:
                return f"No balance sheet data available for {ticker}"
            
            report = f"=== Balance Sheet: {ticker} ({freq}) ===\n\n"
            report += _format_df_for_report(bs)
            return report
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


@tool
def get_cashflow(
    ticker: Annotated[str, "Stock ticker symbol"],
    freq: Annotated[str, "Reporting frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"] = None,
    vendor: Annotated[str, "Data vendor: 'yfinance' or 'alpha_vantage'"] = "yfinance",
) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol.
    
    Args:
        ticker: Stock ticker symbol
        freq: Reporting frequency ('annual' or 'quarterly')
        curr_date: Current date (optional, for context)
        vendor: Data vendor to use
    
    Returns:
        Formatted string containing cash flow statement data
    """
    try:
        if vendor == "alpha_vantage":
            return _make_alpha_vantage_request("CASH_FLOW", ticker)
        else:
            # Use yfinance
            stock = yf.Ticker(ticker)
            if freq == "annual":
                cf = stock.cashflow
            else:
                cf = stock.quarterly_cashflow
            
            if cf.empty:
                return f"No cash flow data available for {ticker}"
            
            report = f"=== Cash Flow Statement: {ticker} ({freq}) ===\n\n"
            report += _format_df_for_report(cf)
            return report
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


@tool
def get_income_statement(
    ticker: Annotated[str, "Stock ticker symbol"],
    freq: Annotated[str, "Reporting frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"] = None,
    vendor: Annotated[str, "Data vendor: 'yfinance' or 'alpha_vantage'"] = "yfinance",
) -> str:
    """
    Retrieve income statement data for a given ticker symbol.
    
    Args:
        ticker: Stock ticker symbol
        freq: Reporting frequency ('annual' or 'quarterly')
        curr_date: Current date (optional, for context)
        vendor: Data vendor to use
    
    Returns:
        Formatted string containing income statement data
    """
    try:
        if vendor == "alpha_vantage":
            return _make_alpha_vantage_request("INCOME_STATEMENT", ticker)
        else:
            # Use yfinance
            stock = yf.Ticker(ticker)
            if freq == "annual":
                is_stmt = stock.financials
            else:
                is_stmt = stock.quarterly_financials
            
            if is_stmt.empty:
                return f"No income statement data available for {ticker}"
            
            report = f"=== Income Statement: {ticker} ({freq}) ===\n\n"
            report += _format_df_for_report(is_stmt)
            return report
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


# --- Structured data fetchers for canonical reports (same keys for every ticker) ---

# Map yfinance DataFrame index names (as they appear) to canonical schema names
_BS_INDEX_MAP = {
    "Total Assets": "Total Assets",
    "totalAssets": "Total Assets",
    "Total Liabilities": "Total Liabilities",
    "totalLiabilities": "Total Liabilities",
    "Total Liabilities Net Minority Interest": "Total Liabilities",
    "Total Stockholder Equity": "Total Equity",
    "totalStockholderEquity": "Total Equity",
    "Total Equity Gross Minority Interest": "Total Equity",
    "Cash And Cash Equivalents": "Cash And Cash Equivalents",
    "cashAndCashEquivalents": "Cash And Cash Equivalents",
    "Net Receivables": "Accounts Receivable",
    "netReceivables": "Accounts Receivable",
    "Accounts Receivable": "Accounts Receivable",
    "Inventory": "Inventory",
    "inventory": "Inventory",
    "Total Current Assets": "Total Current Assets",
    "totalCurrentAssets": "Total Current Assets",
}
_IS_INDEX_MAP = {
    "Total Revenue": "Total Revenue",
    "totalRevenue": "Total Revenue",
    "Cost Of Revenue": "Cost Of Revenue",
    "costOfRevenue": "Cost Of Revenue",
    "Gross Profit": "Gross Profit",
    "grossProfit": "Gross Profit",
    "Operating Income": "Operating Income",
    "operatingIncome": "Operating Income",
    "Net Income": "Net Income",
    "netIncome": "Net Income",
}
_CF_INDEX_MAP = {
    "Operating Cash Flow": "Operating Cash Flow",
    "operatingCashFlow": "Operating Cash Flow",
    "Cash Flow From Continuing Operating Activities": "Operating Cash Flow",
    "Investing Cash Flow": "Investing Cash Flow",
    "investingCashFlow": "Investing Cash Flow",
    "Cash Flow From Continuing Investing Activities": "Investing Cash Flow",
    "Financing Cash Flow": "Financing Cash Flow",
    "financingCashFlow": "Financing Cash Flow",
    "Cash Flow From Continuing Financing Activities": "Financing Cash Flow",
    "Net Change In Cash": "Net Change In Cash",
    "netChangeInCash": "Net Change In Cash",
    "Change In Cash And Cash Equivalents": "Net Change In Cash",
}


def _series_to_latest_value(series) -> str:
    """First non-null value from a series or scalar, formatted."""
    if series is None:
        return "N/A"
    if getattr(series, "empty", False):
        return "N/A"
    if hasattr(series, "iloc"):
        for i in range(len(series)):
            v = series.iloc[i]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                return _format_financial_value(v)
        return "N/A"
    return _format_financial_value(series)


def fetch_fundamentals_data(ticker: str, try_alpha_vantage: bool = True) -> dict:
    """Return a dict with canonical keys for Company Overview and Key Metrics. Uses N/A when missing."""
    out = {}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        retrieved_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        out["Data retrieved at"] = retrieved_at

        # Share price
        sp = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if sp is None or (isinstance(sp, float) and (pd.isna(sp) or sp <= 0)):
            out["Share Price"] = "N/A"
        else:
            out["Share Price"] = f"${float(sp):,.2f}"

        out["Company Name"] = info.get("longName") or info.get("shortName") or "N/A"
        out["Sector"] = info.get("sector") or "N/A"
        out["Industry"] = info.get("industry") or "N/A"
        mc = info.get("marketCap")
        out["Market Cap"] = "$" + _format_financial_value(mc) if mc is not None and not (isinstance(mc, float) and pd.isna(mc)) else "N/A"
        ev = info.get("enterpriseValue")
        out["Enterprise Value"] = "$" + _format_financial_value(ev) if ev is not None and not (isinstance(ev, float) and pd.isna(ev)) else "N/A"

        def _ratio(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "N/A"
            return f"{float(v):.2f}" if isinstance(v, (int, float)) else str(v)

        def _pct(v):
            if v is None or (isinstance(v, float) and (pd.isna(v) or v == 0)):
                return "N/A"
            return f"{float(v)*100:.2f}%"

        out["P/E Ratio"] = _ratio(info.get("trailingPE"))
        out["Forward P/E"] = _ratio(info.get("forwardPE"))
        # PEG: use pegRatio if present, else compute PEG = P/E / (earnings growth * 100)
        peg = info.get("pegRatio")
        if peg is not None and not (isinstance(peg, float) and pd.isna(peg)):
            out["PEG Ratio"] = f"{float(peg):.2f}"
        else:
            pe_val = info.get("trailingPE")
            eg = info.get("earningsGrowth")
            if pe_val is not None and eg is not None and not (pd.isna(pe_val) or pd.isna(eg)) and float(eg) != 0:
                try:
                    out["PEG Ratio"] = f"{float(pe_val) / (float(eg) * 100):.2f}"
                except Exception:
                    out["PEG Ratio"] = "N/A"
            else:
                out["PEG Ratio"] = "N/A"
        out["Price/Book"] = _ratio(info.get("priceToBook"))
        out["Price/Sales"] = _ratio(info.get("priceToSalesTrailing12Months"))
        out["EV/Revenue"] = _ratio(info.get("enterpriseToRevenue"))
        out["EV/EBITDA"] = _ratio(info.get("enterpriseToEbitda"))
        out["Profit Margin"] = _pct(info.get("profitMargins"))
        out["Operating Margin"] = _pct(info.get("operatingMargins"))
        out["ROE"] = _pct(info.get("returnOnEquity"))
        out["ROA"] = _pct(info.get("returnOnAssets"))
        out["Current Ratio"] = _ratio(info.get("currentRatio"))
        out["Quick Ratio"] = _ratio(info.get("quickRatio"))
        out["Debt/Equity"] = _ratio(info.get("debtToEquity"))
        cps = info.get("totalCashPerShare")
        out["Cash per Share"] = f"${float(cps):,.2f}" if cps is not None and not (isinstance(cps, float) and pd.isna(cps)) else "N/A"
        bv = info.get("bookValue")
        out["Book Value"] = f"${float(bv):,.2f}" if bv is not None and not (isinstance(bv, float) and pd.isna(bv)) else "N/A"
        out["Revenue Growth"] = _pct(info.get("revenueGrowth"))
        out["Earnings Growth"] = _pct(info.get("earningsGrowth"))

        # ── Piotroski F-Score (Change 2) ──────────────────────────────────
        # 9-point financial health score proven to generate ~23% alpha annually
        # (Piotroski 2000; confirmed in ML studies through 2024)
        # Score interpretation: 7-9 = Strong, 4-6 = Average, 0-3 = Weak
        try:
            fscore = 0
            criteria = {}

            roa = info.get("returnOnAssets")
            cfo = info.get("operatingCashflows") or info.get("freeCashflow")
            roa_f = float(roa) if roa is not None and not (isinstance(roa, float) and pd.isna(roa)) else None
            cfo_f = float(cfo) if cfo is not None and not (isinstance(cfo, float) and pd.isna(cfo)) else None

            # F1: ROA > 0 (profitable)
            if roa_f is not None and roa_f > 0:
                fscore += 1; criteria["F1_ROA_positive"] = "PASS"
            else:
                criteria["F1_ROA_positive"] = "FAIL"

            # F2: Operating Cash Flow > 0
            if cfo_f is not None and cfo_f > 0:
                fscore += 1; criteria["F2_CFO_positive"] = "PASS"
            else:
                criteria["F2_CFO_positive"] = "FAIL"

            # F3: Earnings Growth > 0 (ROA improving — proxy via earningsGrowth)
            eg = info.get("earningsGrowth")
            eg_f = float(eg) if eg is not None and not (isinstance(eg, float) and pd.isna(eg)) else None
            if eg_f is not None and eg_f > 0:
                fscore += 1; criteria["F3_ROA_improving"] = "PASS"
            else:
                criteria["F3_ROA_improving"] = "FAIL"

            # F4: Quality of earnings (CFO/Assets > ROA — accruals)
            ta = info.get("totalAssets")
            if roa_f is not None and cfo_f is not None and ta is not None:
                ta_f = float(ta)
                if ta_f > 0 and (cfo_f / ta_f) > roa_f:
                    fscore += 1; criteria["F4_earnings_quality"] = "PASS"
                else:
                    criteria["F4_earnings_quality"] = "FAIL"
            else:
                criteria["F4_earnings_quality"] = "N/A"

            # F5: Debt not increasing (low/decreasing leverage)
            de = info.get("debtToEquity")
            de_f = float(de) if de is not None and not (isinstance(de, float) and pd.isna(de)) else None
            if de_f is not None and de_f < 100:   # < 100% D/E = healthy
                fscore += 1; criteria["F5_leverage_ok"] = "PASS"
            else:
                criteria["F5_leverage_ok"] = "FAIL"

            # F6: Current ratio >= 1.0 (liquid)
            cr = info.get("currentRatio")
            cr_f = float(cr) if cr is not None and not (isinstance(cr, float) and pd.isna(cr)) else None
            if cr_f is not None and cr_f >= 1.0:
                fscore += 1; criteria["F6_current_ratio_ok"] = "PASS"
            else:
                criteria["F6_current_ratio_ok"] = "FAIL"

            # F7: Profit margin positive (operational efficiency)
            pm = info.get("profitMargins")
            pm_f = float(pm) if pm is not None and not (isinstance(pm, float) and pd.isna(pm)) else None
            if pm_f is not None and pm_f > 0:
                fscore += 1; criteria["F7_profitable"] = "PASS"
            else:
                criteria["F7_profitable"] = "FAIL"

            # F8: Revenue growth positive (top-line growth)
            rg = info.get("revenueGrowth")
            rg_f = float(rg) if rg is not None and not (isinstance(rg, float) and pd.isna(rg)) else None
            if rg_f is not None and rg_f > 0:
                fscore += 1; criteria["F8_revenue_growing"] = "PASS"
            else:
                criteria["F8_revenue_growing"] = "FAIL"

            # F9: Operating margin positive (asset efficiency)
            om = info.get("operatingMargins")
            om_f = float(om) if om is not None and not (isinstance(om, float) and pd.isna(om)) else None
            if om_f is not None and om_f > 0:
                fscore += 1; criteria["F9_operating_efficient"] = "PASS"
            else:
                criteria["F9_operating_efficient"] = "FAIL"

            strength = "Strong" if fscore >= 7 else ("Average" if fscore >= 4 else "Weak")
            out["Piotroski F-Score"] = f"{fscore}/9 ({strength})"
            out["Piotroski Criteria"] = criteria

        except Exception:
            out["Piotroski F-Score"] = "N/A"
            out["Piotroski Criteria"] = {}

        return out
    except Exception:
        all_keys = (
            "Company Name", "Sector", "Industry", "Share Price", "Market Cap", "Enterprise Value", "Data retrieved at",
            "P/E Ratio", "Forward P/E", "PEG Ratio", "Price/Book", "Price/Sales", "EV/Revenue", "EV/EBITDA",
            "Profit Margin", "Operating Margin", "ROE", "ROA", "Current Ratio", "Quick Ratio", "Debt/Equity",
            "Cash per Share", "Book Value", "Revenue Growth", "Earnings Growth"
        )
        return {k: "N/A" for k in all_keys}


def _df_to_canonical_dict(df: pd.DataFrame, index_map: dict, canonical_keys: list) -> dict:
    """Take first column (most recent period) of df, map index to canonical names, return dict with all canonical keys."""
    result = {k: "N/A" for k in canonical_keys}
    if df is None or df.empty:
        return result
    first_col = df.iloc[:, 0]
    for idx in df.index:
        idx_str = str(idx).strip()
        canonical = index_map.get(idx_str) or (idx_str if idx_str in result else None)
        if canonical and canonical in result:
            try:
                val = first_col.loc[idx]
                result[canonical] = _series_to_latest_value(val)
            except Exception:
                result[canonical] = "N/A"
    return result


def fetch_balance_sheet_data(ticker: str, freq: str = "quarterly", try_alpha_vantage: bool = True) -> dict:
    """Return dict with canonical balance sheet keys. Tries yfinance, then Alpha Vantage if empty."""
    from report_schema import BALANCE_SHEET_FIELDS
    try:
        stock = yf.Ticker(ticker)
        bs = stock.quarterly_balance_sheet if freq == "quarterly" else stock.balance_sheet
        if bs is not None and not bs.empty:
            return _df_to_canonical_dict(bs, _BS_INDEX_MAP, BALANCE_SHEET_FIELDS)
    except Exception:
        pass
    if try_alpha_vantage and os.getenv("ALPHA_VANTAGE_API_KEY"):
        try:
            raw = _make_alpha_vantage_request("BALANCE_SHEET", ticker)
            data = json.loads(raw)
            reports = data.get("quarterlyReports", data.get("annualReports", []))[:1]
            if reports:
                r = reports[0]
                result = {k: "N/A" for k in BALANCE_SHEET_FIELDS}
                result["Total Assets"] = _format_financial_value(float(r.get("totalAssets", 0) or 0))
                result["Total Liabilities"] = _format_financial_value(float(r.get("totalLiabilities", 0) or 0))
                result["Total Equity"] = _format_financial_value(float(r.get("totalStockholderEquity", 0) or 0))
                result["Cash And Cash Equivalents"] = _format_financial_value(float(r.get("cashAndCashEquivalents", 0) or 0))
                result["Accounts Receivable"] = _format_financial_value(float(r.get("netReceivables", 0) or 0))
                result["Inventory"] = _format_financial_value(float(r.get("inventory", 0) or 0))
                result["Total Current Assets"] = _format_financial_value(float(r.get("totalCurrentAssets", 0) or 0))
                return result
        except Exception:
            pass
    return {k: "N/A" for k in BALANCE_SHEET_FIELDS}


def fetch_cashflow_data(ticker: str, freq: str = "quarterly", try_alpha_vantage: bool = True) -> dict:
    """Return dict with canonical cash flow keys. Tries yfinance, then Alpha Vantage if empty."""
    from report_schema import CASH_FLOW_FIELDS
    try:
        stock = yf.Ticker(ticker)
        cf = stock.quarterly_cashflow if freq == "quarterly" else stock.cashflow
        if cf is not None and not cf.empty:
            return _df_to_canonical_dict(cf, _CF_INDEX_MAP, CASH_FLOW_FIELDS)
    except Exception:
        pass
    if try_alpha_vantage and os.getenv("ALPHA_VANTAGE_API_KEY"):
        try:
            raw = _make_alpha_vantage_request("CASH_FLOW", ticker)
            data = json.loads(raw)
            reports = data.get("quarterlyReports", data.get("annualReports", []))[:1]
            if reports:
                r = reports[0]
                result = {k: "N/A" for k in CASH_FLOW_FIELDS}
                result["Operating Cash Flow"] = _format_financial_value(float(r.get("operatingCashflow", 0) or 0))
                result["Investing Cash Flow"] = _format_financial_value(float(r.get("cashflowFromInvestment", 0) or 0))
                result["Financing Cash Flow"] = _format_financial_value(float(r.get("cashflowFromFinancing", 0) or 0))
                result["Net Change In Cash"] = _format_financial_value(float(r.get("changeInCashAndCashEquivalents", 0) or 0))
                return result
        except Exception:
            pass
    return {k: "N/A" for k in CASH_FLOW_FIELDS}


def fetch_income_statement_data(ticker: str, freq: str = "quarterly", try_alpha_vantage: bool = True) -> dict:
    """Return dict with canonical income statement keys. Tries yfinance, then Alpha Vantage if empty."""
    from report_schema import INCOME_STATEMENT_FIELDS
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.quarterly_financials if freq == "quarterly" else stock.financials
        if is_stmt is not None and not is_stmt.empty:
            return _df_to_canonical_dict(is_stmt, _IS_INDEX_MAP, INCOME_STATEMENT_FIELDS)
    except Exception:
        pass
    if try_alpha_vantage and os.getenv("ALPHA_VANTAGE_API_KEY"):
        try:
            raw = _make_alpha_vantage_request("INCOME_STATEMENT", ticker)
            data = json.loads(raw)
            reports = data.get("quarterlyReports", data.get("annualReports", []))[:1]
            if reports:
                r = reports[0]
                result = {k: "N/A" for k in INCOME_STATEMENT_FIELDS}
                result["Total Revenue"] = _format_financial_value(float(r.get("totalRevenue", 0) or 0))
                result["Cost Of Revenue"] = _format_financial_value(float(r.get("costOfRevenue", 0) or 0))
                result["Gross Profit"] = _format_financial_value(float(r.get("grossProfit", 0) or 0))
                result["Operating Income"] = _format_financial_value(float(r.get("operatingIncome", 0) or 0))
                result["Net Income"] = _format_financial_value(float(r.get("netIncome", 0) or 0))
                return result
        except Exception:
            pass
    return {k: "N/A" for k in INCOME_STATEMENT_FIELDS}
