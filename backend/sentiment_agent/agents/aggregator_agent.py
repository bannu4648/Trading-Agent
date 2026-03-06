"""
Aggregator that fuses all four sentiment agent scores into one composite.

Uses configurable weights from settings. Purely mathematical — no LLM calls.
"""
from sentiment_agent.config.settings import settings


class AggregatorAgent:
    """
    Takes the raw outputs from each sentiment agent, applies weighted
    averaging, and produces a final score + label + confidence.

    Change 4 improvements:
    - Web score = 0.0 is treated as missing (weight redistributed to other sources)
    - Analyst confidence floor: strong analyst consensus boosts minimum confidence
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

            # Web-zero detection: if web consistently returns 0.0 and flag is set,
            # treat it as missing data and skip (weight redistributed to others)
            if (agent_name == "web_search"
                    and score == 0.0
                    and getattr(settings, "web_zero_means_missing", False)):
                breakdown[agent_name] = {
                    "score": 0.0,
                    "label": result.get("label", "neutral"),
                    "weight": 0.0,  # excluded
                    "reasoning": result.get("reasoning", "") or "Excluded: zero score treated as missing data",
                }
                continue

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
            agreement = max(0.3, 1.0 - spread * 0.7)
        else:
            agreement = 0.5

        # base confidence from signal strength, boosted by agreement
        signal_strength = min(abs(composite) * 1.2, 1.0)
        confidence = round(min((0.3 + signal_strength * 0.7) * agreement, 1.0), 4)

        # Analyst confidence floor (Change 4): strong analyst consensus
        # guarantees a minimum confidence level even if other signals are weak
        analyst_score = float(agent_results.get("analyst_buzz", {}).get("score", 0.0))
        threshold = getattr(settings, "analyst_confidence_threshold", 0.7)
        floor = getattr(settings, "analyst_confidence_floor", 0.55)
        if abs(analyst_score) >= threshold:
            confidence = max(confidence, floor)

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

