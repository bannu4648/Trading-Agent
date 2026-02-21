"""
Scrapes DuckDuckGo HTML search results for a stock ticker.
No API key needed -- we just parse the HTML response.
"""
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _search_ddg(query: str, max_results: int = 4) -> list[str]:
    """Run a single DuckDuckGo HTML search and return title+snippet strings."""
    url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        snippets = []
        results = soup.find_all("div", class_="result__body")
        for result in results[:max_results]:
            title_tag = result.find("a", class_="result__a")
            snippet_tag = result.find("a", class_="result__snippet")
            title = title_tag.get_text(strip=True) if title_tag else ""
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            if title or snippet:
                snippets.append(f"{title}: {snippet}".strip(": "))
        return snippets
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for query '{query}': {e}")
        return []


def fetch_web_snippets(ticker: str, company_name: str = "", max_results: int = 8) -> list[str]:
    """
    Run multiple DuckDuckGo searches with different query angles to get a
    more balanced set of web snippets. Using just one query often skews
    results if the top results happen to be all bullish or all bearish.
    """
    name = company_name or ticker

    # two different search angles to reduce single-query bias
    queries = [
        f"{name} {ticker} stock analyst outlook forecast 2026",
        f"{name} {ticker} stock news sentiment risks 2026",
    ]

    all_snippets = []
    seen = set()
    per_query = max_results // len(queries)

    for query in queries:
        for snippet in _search_ddg(query, max_results=per_query + 2):
            # deduplicate across queries
            if snippet not in seen:
                seen.add(snippet)
                all_snippets.append(snippet)

    return all_snippets[:max_results]
