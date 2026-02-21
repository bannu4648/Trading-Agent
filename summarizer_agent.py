"""
Summarizer Agent - synthesizes technical and sentiment analysis results
into a final trading recommendation.
"""

import logging
from typing import Any, Dict
from sentiment_agent.models.gemini_client import gemini_client

logger = logging.getLogger(__name__)

SUMMARIZER_PROMPT = """
You are a Senior Investment Strategist. Your task is to synthesize technical analysis and sentiment analysis for a specific stock into a clear, actionable trading suggestion.

TECHNICAL ANALYSIS HIGHLIGHTS:
{technical_summary}

SENTIMENT ANALYSIS HIGHLIGHTS:
Score: {sentiment_score} ({sentiment_label})
Confidence: {sentiment_confidence}
Key Themes: {sentiment_themes}
Bull vs Bear: {sentiment_resolution}

Please provide:
1. **Overall Trend**: A concise summary of the prevailing direction.
2. **Analysis Synthesis**: How the technical and sentiment data confirm or contradict each other.
3. **Recommendation**: A suggested action (e.g., Buy, Hold, Avoid, Sell) with a brief justification.
4. **Key Risks**: What should a trader watch out for?

Respond in clean Markdown format. Be professional, objective, and data-driven.
"""

class SummarizerAgent:
    def __init__(self):
        self.llm = gemini_client

    def run(self, ticker: str, combined_data: Dict[str, Any]) -> str:
        """
        Synthesize results for a given ticker from the combined data dict.
        """
        results = combined_data.get("results", {}).get(ticker, {})
        tech = results.get("technical", {})
        sent = results.get("sentiment", {})

        # Extract technical summary
        tech_summary = tech.get("summary", "No technical summary available.")
        
        # Extract sentiment details
        sent_agg = sent # The sentiment dict itself has the labels
        score = sent.get("sentiment_score", "N/A")
        label = sent.get("sentiment_label", "N/A")
        confidence = sent.get("confidence", "N/A")
        
        sources = sent.get("sources", {})
        news = sources.get("news_sentiment", {})
        themes = ", ".join(news.get("key_themes", [])) if news.get("key_themes") else "None"
        
        debate = sent.get("debate", {})
        resolution = debate.get("resolution", "No consensus reached.")

        prompt = SUMMARIZER_PROMPT.format(
            technical_summary=tech_summary,
            sentiment_score=score,
            sentiment_label=label,
            sentiment_confidence=confidence,
            sentiment_themes=themes,
            sentiment_resolution=resolution
        )

        logger.info(f"Summarizing results for {ticker}...")
        try:
            summary = self.llm.generate(prompt)
            return summary
        except Exception as e:
            logger.error(f"Symmetry generation failed for {ticker}: {e}")
            return "Failed to generate synthesis summary."

if __name__ == "__main__":
    # Test with a dummy result if needed
    pass
