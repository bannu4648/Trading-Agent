"""
All the prompt templates used by the sentiment agents.
Kept in one place so they're easy to tweak without touching agent logic.

Design decisions based on recent prompt engineering research:
- Calibration anchors so the LLM knows what different scores mean
  (The Prompt Report, Schulhoff et al. 2024)
- Numerical attention hints for financial data
  (Expert-Designed Hints, arXiv:2409.17174)
- No chain-of-thought -- it actually hurts sentiment classification
  (Vamvourellis & Mehta, 2025, arXiv:2506.04574)
- Structured JSON output for all prompts
  (The Prompt Report ranks this as the most reliably beneficial technique)
"""

# shared scoring guide used across agent prompts -- keeps calibration consistent
_SCORING_GUIDE = """Scoring guide (use this to calibrate your score):
  0.7 to 1.0  = strongly positive (e.g. major earnings beat, analyst upgrades across the board)
  0.3 to 0.7  = moderately positive (e.g. generally favourable news, mild optimism)
  -0.3 to 0.3 = neutral or mixed signals
  -0.7 to -0.3 = moderately negative (e.g. earnings miss, downgrades)
  -1.0 to -0.7 = strongly negative (e.g. fraud allegations, major lawsuit, mass layoffs)"""


NEWS_SENTIMENT_PROMPT = f"""You are a financial sentiment analyst. Analyze the following news headlines for the stock ticker {{ticker}}.

Headlines:
{{headlines}}

Pay close attention to numerical values such as earnings figures, revenue numbers, and percentage changes -- these are often the strongest sentiment signals.

{_SCORING_GUIDE}

Return a JSON object with exactly these fields:
- "score": float between -1.0 and 1.0
- "label": one of "positive", "negative", or "neutral"
- "reasoning": one sentence explaining the key sentiment driver
- "key_themes": list of up to 3 short strings (e.g. ["earnings beat", "product launch"])

Respond with ONLY the JSON object, no markdown, no extra text."""


SOCIAL_SENTIMENT_PROMPT = f"""You are a financial sentiment analyst specializing in retail investor sentiment. Analyze the following Reddit/social media data for stock ticker {{ticker}}.

ApeWisdom Data (Reddit aggregated):
- Mentions in last 24h: {{mentions}}
- Upvotes in last 24h: {{upvotes}}
- Current rank among most-discussed stocks: #{{rank}}
- Rank change vs yesterday: {{rank_change}} (positive = rising interest)

CRITICAL: These metrics measure ATTENTION VOLUME, not sentiment direction. Interpret carefully:
- Low mentions / high rank does NOT mean negative sentiment. It often just means the stock isn't a meme or speculative play. Large-cap stocks like AAPL, MSFT, META often rank low on Reddit because institutional investors (not Redditors) drive their price.
- Only score negatively if there are explicit signals of bearish retail sentiment, like a sharp drop in mentions after a surge (interest fading after hype), or if the context suggests panic selling.
- A stock with low Reddit buzz should generally get a NEUTRAL score (near 0), not a negative score.
- High mentions + high upvotes = strong retail interest (could be bullish or bearish -- use context).
- Top-10 stocks typically get 500+ mentions per day. Most established large-caps sit at rank 50-200 normally.

{_SCORING_GUIDE}

Return a JSON object with exactly these fields:
- "score": float between -1.0 and 1.0
- "label": one of "positive", "negative", or "neutral"
- "reasoning": one sentence explaining the social sentiment signal

Respond with ONLY the JSON object, no markdown, no extra text."""


ANALYST_BUZZ_PROMPT = f"""You are a financial sentiment analyst. Analyze the following Wall Street analyst data for stock ticker {{ticker}}.

Analyst Data:
{{analyst_data}}

Pay close attention to numerical values: price target vs current price spread, the ratio of buy/hold/sell ratings, and the number of analysts covering the stock. A wide consensus among many analysts is a stronger signal than a few scattered opinions.

{_SCORING_GUIDE}

Return a JSON object with exactly these fields:
- "score": float between -1.0 and 1.0
- "label": one of "positive", "negative", or "neutral"
- "reasoning": one sentence explaining the analyst sentiment

Respond with ONLY the JSON object, no markdown, no extra text."""


WEB_SENTIMENT_PROMPT = f"""You are a financial sentiment analyst. Analyze the following web search snippets about stock ticker {{ticker}}.

Web Snippets:
{{snippets}}

Focus on the overall tone across all snippets. Look for recurring themes and pay attention to any concrete numbers, forecasts, or analyst opinions mentioned in the text.

{_SCORING_GUIDE}

Return a JSON object with exactly these fields:
- "score": float between -1.0 and 1.0
- "label": one of "positive", "negative", or "neutral"
- "reasoning": one sentence explaining the overall web sentiment

Respond with ONLY the JSON object, no markdown, no extra text."""


DEBATE_PROMPT = """You are a senior financial analyst moderating a sentiment debate for stock ticker {ticker}.

The following specialized agents have produced these sentiment readings:
{agent_results}

Your task:
1. Identify the STRONGEST arguments for a bullish outlook (the bull case). Cite specific evidence from the agent outputs.
2. Identify the STRONGEST arguments for a bearish or cautious outlook (the bear case). Cite specific evidence.
3. Weigh the evidence: which side has more concrete, data-backed support? Write a resolution explaining your judgement.

Return a JSON object with exactly these fields:
- "bull_case": string (1-2 sentences, cite specific data points)
- "bear_case": string (1-2 sentences, cite specific data points)
- "resolution": string (1 sentence, state which side wins and why)
- "key_drivers": list of up to 3 short strings naming the most important sentiment drivers

Respond with ONLY the JSON object, no markdown, no extra text."""


SUMMARY_PROMPT = """You are a senior investment analyst. Summarize the overall market sentiment for stock ticker {ticker}.

Sentiment Score: {sentiment_score} (range: -1.0 to 1.0)
Sentiment Label: {sentiment_label}
Confidence: {confidence} (range: 0.0 to 1.0, higher = more agreement across sources)

Debate Resolution: {resolution}

Return a JSON object with exactly these fields:
- "ticker": the stock ticker
- "sentiment": the sentiment label
- "confidence": the confidence value
- "summary": a concise 2-3 sentence summary of the sentiment outlook, written in a factual and objective tone

Respond with ONLY the JSON object, no markdown, no extra text."""
