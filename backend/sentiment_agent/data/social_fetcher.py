"""
Fetches social/retail investor sentiment data from ApeWisdom.
ApeWisdom aggregates Reddit mentions across r/wallstreetbets, r/stocks, etc.
No authentication required which is nice.
"""
import logging
import requests

logger = logging.getLogger(__name__)

APEWISDOM_BASE = "https://apewisdom.io/api/v1.0"


def fetch_apewisdom(ticker: str) -> dict:
    """
    Look up the ticker in ApeWisdom's top stocks list.
    Returns mentions, upvotes, rank info. Falls back to zeros if
    the ticker isn't trending or the API is down.
    """
    url = f"{APEWISDOM_BASE}/filter/all-stocks/page/1"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        ticker_upper = ticker.upper()
        for item in results:
            if item.get("ticker", "").upper() == ticker_upper:
                return {
                    "ticker": ticker_upper,
                    "mentions": item.get("mentions", 0),
                    "upvotes": item.get("upvotes", 0),
                    "rank": item.get("rank", 999),
                    "rank_24h_ago": item.get("rank_24h_ago", 999),
                    "rank_change": item.get("rank_24h_ago", 999) - item.get("rank", 999),
                }
        # ticker not popular enough to be in the top list
        logger.info(f"{ticker} not found in ApeWisdom top results — returning zeros")
        return {
            "ticker": ticker_upper,
            "mentions": 0,
            "upvotes": 0,
            "rank": 999,
            "rank_24h_ago": 999,
            "rank_change": 0,
        }
    except Exception as e:
        logger.error(f"ApeWisdom fetch error for {ticker}: {e}")
        return {
            "ticker": ticker.upper(),
            "mentions": 0,
            "upvotes": 0,
            "rank": 999,
            "rank_24h_ago": 999,
            "rank_change": 0,
        }
