"""
Pulls Reddit mention/upvote data from ApeWisdom and asks the LLM
to interpret the social buzz as a sentiment signal.
"""
from sentiment_agent.agents.base_agent import BaseAgent
from sentiment_agent.data.social_fetcher import fetch_apewisdom
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.config.prompts import SOCIAL_SENTIMENT_PROMPT


class SocialSentimentAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "social_sentiment"

    def run(self, ticker: str) -> dict:
        data = fetch_apewisdom(ticker)

        prompt = SOCIAL_SENTIMENT_PROMPT.format(
            ticker=ticker,
            mentions=data["mentions"],
            upvotes=data["upvotes"],
            rank=data["rank"],
            rank_change=data["rank_change"],
        )
        result = gemini_client.generate_json(prompt)

        result["mentions"] = data["mentions"]
        result["upvotes"] = data["upvotes"]
        result["rank"] = data["rank"]
        result["score"] = float(max(-1.0, min(1.0, result.get("score", 0.0))))
        return result
