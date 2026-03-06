"""
Scrapes news headlines from Finviz and Yahoo Finance for a given ticker.
Results are combined and deduplicated before being passed to the news agent.
"""
import logging
import requests
from bs4 import BeautifulSoup
import yfinance as yf

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_finviz_headlines(ticker: str, max_headlines: int = 10) -> list[str]:
    """Scrape the news table on Finviz's quote page."""
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        news_table = soup.find("table", id="news-table")
        if not news_table:
            logger.warning(f"No news table found on Finviz for {ticker}")
            return []
        headlines = []
        for row in news_table.find_all("tr")[:max_headlines]:
            link = row.find("a")
            if link:
                headlines.append(link.get_text(strip=True))
        return headlines
    except Exception as e:
        logger.error(f"Finviz fetch error for {ticker}: {e}")
        return []


def fetch_yahoo_headlines(ticker: str, max_headlines: int = 5) -> list[str]:
    """Get recent news from Yahoo Finance through yfinance."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        return [
            item.get("content", {}).get("title", "")
            for item in news[:max_headlines]
            if item.get("content", {}).get("title")
        ]
    except Exception as e:
        logger.error(f"Yahoo Finance news fetch error for {ticker}: {e}")
        return []


def fetch_all_headlines(ticker: str) -> list[str]:
    """Combine both sources and deduplicate."""
    headlines = fetch_finviz_headlines(ticker) + fetch_yahoo_headlines(ticker)
    seen = set()
    unique = []
    for h in headlines:
        if h and h not in seen:
            seen.add(h)
            unique.append(h)
    return unique
