"""
Aggregator that fuses all four sentiment agent scores into one composite.

Uses configurable weights from settings. Purely mathematical — no LLM calls.
"""
from sentiment_agent.config.settings import settings


class AggregatorAgent:
    """
    Takes the raw outputs from each sentiment agent, applies weighted
    averaging, and produces a final score + label + confidence.
    """

    WEIGHT_MAP = {
        "news_sentiment": "weight_news",
        "social_sentiment": "weight_social",
        "analyst_buzz": "weight_analyst",
        "web_search": "weight_web",
    }

    def run(self, agent_results: dict) -> dict:
        """
        agent_results should look like {agent_name: {score, label, ...}}.
        Returns composite score, label, confidence, and per-source breakdown.
        """
        composite = 0.0
        total_weight = 0.0
        breakdown = {}

        for agent_name, weight_attr in self.WEIGHT_MAP.items():
            weight = getattr(settings, weight_attr, 0.0)
            result = agent_results.get(agent_name, {})
            score = float(result.get("score", 0.0))
            composite += score * weight
            total_weight += weight
            breakdown[agent_name] = {
                "score": round(score, 4),
                "label": result.get("label", "neutral"),
                "weight": weight,
                "reasoning": result.get("reasoning", ""),
            }

        # normalize if weights don't perfectly sum to 1
        if total_weight > 0:
            composite /= total_weight

        composite = round(max(-1.0, min(1.0, composite)), 4)
        label = self._score_to_label(composite)

        # confidence based on two factors:
        # 1) signal strength -- stronger composite = more confident
        # 2) agent agreement -- if all agents point the same way, confidence goes up;
        #    if they're all over the place, it goes down
        scores = [float(r.get("score", 0.0)) for r in agent_results.values() if r]
        if len(scores) > 1:
            mean = sum(scores) / len(scores)
            spread = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
            # spread ranges from 0 (perfect agreement) to ~1 (total disagreement)
            # agreement factor: 1.0 when spread=0, drops toward 0.3 at spread=1
            agreement = max(0.3, 1.0 - spread * 0.7)
        else:
            agreement = 0.5

        # base confidence from signal strength, boosted by agreement
        signal_strength = min(abs(composite) * 1.2, 1.0)
        confidence = round(min((0.3 + signal_strength * 0.7) * agreement, 1.0), 4)

        return {
            "sentiment_score": composite,
            "sentiment_label": label,
            "confidence": confidence,
            "sources": breakdown,
        }

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score >= 0.15:
            return "POSITIVE"
        elif score <= -0.15:
            return "NEGATIVE"
        return "NEUTRAL"
