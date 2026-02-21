"""
Searches DuckDuckGo for recent articles about a stock and uses
the LLM to score the sentiment of the search results.
"""
from sentiment_agent.agents.base_agent import BaseAgent
from sentiment_agent.data.web_fetcher import fetch_web_snippets
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.config.prompts import WEB_SENTIMENT_PROMPT
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class WebSentimentAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "web_search"

    def run(self, ticker: str) -> dict:
        # try to grab the company name so the search query is better
        company_name = ""
        try:
            info = yf.Ticker(ticker).info
            company_name = info.get("shortName", "") or info.get("longName", "")
        except Exception:
            pass

        snippets = fetch_web_snippets(ticker, company_name=company_name)

        if not snippets:
            return {
                "score": 0.0,
                "label": "neutral",
                "reasoning": "No web search results found.",
                "snippets_analyzed": 0,
            }

        snippets_text = "\n".join(f"- {s}" for s in snippets)
        prompt = WEB_SENTIMENT_PROMPT.format(ticker=ticker, snippets=snippets_text)
        result = gemini_client.generate_json(prompt)

        result["snippets_analyzed"] = len(snippets)
        result["score"] = float(max(-1.0, min(1.0, result.get("score", 0.0))))
        return result
