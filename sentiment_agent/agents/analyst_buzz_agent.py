"""
Fetches Wall St analyst recommendations from Finnhub and has the LLM
interpret the overall analyst sentiment (upgrades, downgrades, targets).
"""
import json
from sentiment_agent.agents.base_agent import BaseAgent
from sentiment_agent.data.analyst_fetcher import fetch_analyst_data
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.config.prompts import ANALYST_BUZZ_PROMPT


class AnalystBuzzAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "analyst_buzz"

    def run(self, ticker: str) -> dict:
        data = fetch_analyst_data(ticker)

        # nothing useful came back — just return neutral
        if not data["recommendation_key"] or data["recommendation_key"] == "none":
            if not data["recent_actions"]:
                return {
                    "score": 0.0,
                    "label": "neutral",
                    "reasoning": "No analyst data available.",
                    "buy_count": 0,
                    "hold_count": 0,
                    "sell_count": 0,
                }

        # tally up the recent upgrade/downgrade actions
        buy_count = sum(
            1 for a in data["recent_actions"]
            if any(w in (a.get("to_grade") or "").lower() for w in ["buy", "outperform", "overweight", "strong buy"])
        )
        hold_count = sum(
            1 for a in data["recent_actions"]
            if any(w in (a.get("to_grade") or "").lower() for w in ["hold", "neutral", "market perform", "equal"])
        )
        sell_count = sum(
            1 for a in data["recent_actions"]
            if any(w in (a.get("to_grade") or "").lower() for w in ["sell", "underperform", "underweight"])
        )

        # package it up so the LLM has something readable
        analyst_summary = {
            "consensus": data["recommendation_key"],
            "analyst_count": data["analyst_count"],
            "price_target_mean": data["target_mean_price"],
            "price_target_high": data["target_high_price"],
            "price_target_low": data["target_low_price"],
            "current_price": data["current_price"],
            "recent_upgrades": buy_count,
            "recent_holds": hold_count,
            "recent_downgrades": sell_count,
            "recent_actions_sample": data["recent_actions"][:5],
        }

        prompt = ANALYST_BUZZ_PROMPT.format(
            ticker=ticker,
            analyst_data=json.dumps(analyst_summary, indent=2),
        )
        result = gemini_client.generate_json(prompt)

        result["buy_count"] = buy_count
        result["hold_count"] = hold_count
        result["sell_count"] = sell_count
        result["consensus"] = data["recommendation_key"]
        result["score"] = float(max(-1.0, min(1.0, result.get("score", 0.0))))
        return result
