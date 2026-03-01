"""
Synthesizes technical, sentiment, and fundamental results into
a plain-English trading recommendation using an LLM.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sentiment_agent.models.gemini_client import gemini_client

logger = logging.getLogger(__name__)


# Which fundamentals fields actually matter for the synthesis prompt.
# Keeping this short so the LLM doesn't get lost in noise.
_FUNDAMENTALS_KEYS = [
    "Company Name", "Sector", "Share Price", "Market Cap",
    "P/E Ratio", "Forward P/E", "PEG Ratio",
    "Profit Margin", "Operating Margin",
    "ROE", "ROA",
    "Current Ratio", "Debt/Equity",
    "Revenue Growth", "Earnings Growth",
    "Piotroski F-Score",
]

_PROMPT = """\
You are a Senior Investment Strategist. Synthesize the technical, sentiment, \
and fundamental data below into a clear, actionable trading suggestion.

TECHNICAL:
{technical_summary}

SENTIMENT:
Score: {sentiment_score} ({sentiment_label}) | Confidence: {sentiment_confidence}
Key Themes: {sentiment_themes}
Bull vs Bear: {sentiment_resolution}

FUNDAMENTALS:
{fundamentals_summary}

Provide:
1. **Overall Trend** — prevailing direction in one sentence
2. **Analysis Synthesis** — where the three data sources agree or conflict
3. **Recommendation** — Buy / Hold / Avoid / Sell with brief justification
4. **Key Risks** — what to watch for (technical + fundamental)

Reply in clean Markdown. Be concise and data-driven.
"""


class SummarizerAgent:
    """
    Calls an LLM with a structured prompt that combines technical
    indicators, sentiment scores, and fundamental ratios.

    Returns a Markdown string — meant to be shown directly in the dashboard.
    """

    def __init__(self) -> None:
        self.llm = gemini_client
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, ticker: str, combined_data: Dict[str, Any]) -> str:
        """Produce a synthesis string for `ticker` from the shared results dict."""
        self.logger.info(f"[summarizer] Synthesizing {ticker}")

        results = combined_data.get("results", {}).get(ticker, {})
        tech = results.get("technical", {})
        sent = results.get("sentiment", {})
        fund = results.get("fundamentals", {})

        prompt = _PROMPT.format(
            technical_summary=tech.get("summary", "No technical data."),
            sentiment_score=sent.get("sentiment_score", "N/A"),
            sentiment_label=sent.get("sentiment_label", "N/A"),
            sentiment_confidence=sent.get("confidence", "N/A"),
            sentiment_themes=self._extract_themes(sent),
            sentiment_resolution=sent.get("debate", {}).get("resolution", "No consensus."),
            fundamentals_summary=self._format_fundamentals(fund),
        )

        try:
            return self.llm.generate(prompt)
        except Exception as exc:
            self.logger.error(f"[summarizer] LLM call failed for {ticker}: {exc}")
            return "Synthesis unavailable — LLM call failed."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_fundamentals(self, fund: Dict[str, Any]) -> str:
        if not fund:
            return "No fundamental data available."
        lines = [
            f"  {k}: {fund[k]}"
            for k in _FUNDAMENTALS_KEYS
            if fund.get(k) and str(fund[k]) not in ("nan", "N/A", "")
        ]
        return "\n".join(lines) or "No fundamental data available."

    @staticmethod
    def _extract_themes(sent: Dict[str, Any]) -> str:
        news = sent.get("sources", {}).get("news_sentiment", {})
        themes = news.get("key_themes", [])
        return ", ".join(themes) if themes else "None identified"
