"""
Scrapes financial news headlines (Finviz + Yahoo) and asks the LLM
to score the overall sentiment for a given ticker.
"""
from sentiment_agent.agents.base_agent import BaseAgent
from sentiment_agent.data.news_fetcher import fetch_all_headlines
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.config.prompts import NEWS_SENTIMENT_PROMPT


class NewsSentimentAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "news_sentiment"

    def run(self, ticker: str) -> dict:
        headlines = fetch_all_headlines(ticker)
        if not headlines:
            return {
                "score": 0.0,
                "label": "neutral",
                "reasoning": "No headlines found.",
                "sources": 0,
            }

        headlines_text = "\n".join(f"- {h}" for h in headlines)
        prompt = NEWS_SENTIMENT_PROMPT.format(ticker=ticker, headlines=headlines_text)
        result = gemini_client.generate_json(prompt)

        result["sources"] = len(headlines)
        result["score"] = float(max(-1.0, min(1.0, result.get("score", 0.0))))
        return result
