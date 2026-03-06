"""
Runs a "bull vs bear" debate after all sentiment agents have finished.

The idea here is inspired by multi-agent debate papers (Du et al., 2023) --
having the LLM synthesize conflicting signals improves the final quality
compared to just averaging scores blindly.
"""
import json
from sentiment_agent.models.gemini_client import gemini_client
from sentiment_agent.config.prompts import DEBATE_PROMPT


class DebateAgent:
    """
    Receives all agent results and produces a structured debate:
    bull_case, bear_case, resolution, and key_drivers.
    """

    def run(self, ticker: str, agent_results: dict) -> dict:
        # condense each agent's output into something the LLM can digest
        agent_summary = {}
        for name, result in agent_results.items():
            agent_summary[name] = {
                "score": result.get("score", 0.0),
                "label": result.get("label", "neutral"),
                "reasoning": result.get("reasoning", ""),
            }

        prompt = DEBATE_PROMPT.format(
            ticker=ticker,
            agent_results=json.dumps(agent_summary, indent=2),
        )

        try:
            result = gemini_client.generate_json(prompt)
            return {
                "bull_case": result.get("bull_case", ""),
                "bear_case": result.get("bear_case", ""),
                "resolution": result.get("resolution", ""),
                "key_drivers": result.get("key_drivers", []),
            }
        except Exception as e:
            # debate is nice-to-have, not critical
            return {
                "bull_case": "Positive signals from multiple sources.",
                "bear_case": "Some uncertainty remains.",
                "resolution": "Debate unavailable.",
                "key_drivers": [],
            }
