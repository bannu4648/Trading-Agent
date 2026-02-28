"""
Adapter: converts Trading-Agent pipeline output → Trader Agent input schema.

The existing pipeline produces three things per ticker:
  - technical:  signals (direction/strength), indicators (ATR, Bollinger Bands, price)
  - sentiment:  sentiment_score, confidence, debate (bull_case / bear_case / resolution)
  - synthesis:  plain Markdown string — the Summarizer's final recommendation

Interpretation approach:
  signal, conviction_score, expected_return
      → LLM call that reads the synthesis narrative, sentiment debate, and technical
        signals together.  Falls back to formulas if the LLM call fails.

  volatility
      → Always derived from ATR / Bollinger Bands (requires real price data;
        an LLM must not estimate this).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from .models import ResearchTeamOutput, StockRecommendation

logger = logging.getLogger(__name__)

_MAX_EXP_RETURN  =  0.25
_MIN_EXP_RETURN  = -0.25
_DEFAULT_VOLATILITY = 0.25


# ---------------------------------------------------------------------------
# LLM interpretation  (signal + conviction + expected_return)
# ---------------------------------------------------------------------------

_INTERPRETATION_SYSTEM = """You are a quantitative analyst on a professional trading desk.

You will receive a research package for a single stock containing:
  1. synthesis     — the Summarizer Agent's final recommendation (Markdown)
  2. sentiment     — sentiment score, confidence, bull/bear debate, resolution
  3. tech_signals  — list of technical signals with direction and strength

Your job: extract three fields as a JSON object, nothing else.

Rules:
- signal: "BUY", "SELL", or "HOLD"
    Read the synthesis Recommendation section first — it is the highest-priority input.
    If the synthesis says "Avoid", "Sell", or "Do not buy" → SELL.
    If the synthesis says "Buy", "Accumulate", "Go long" → BUY.
    If the synthesis says "Hold", "Watch", "Neutral", or is ambiguous → HOLD.
    Only use technical / sentiment as tiebreaker when the synthesis is genuinely unclear.

- conviction_score: float 0.0–10.0
    How strongly does the evidence support the chosen signal?
    Consider: agreement between synthesis/technical/sentiment, signal strength values,
    sentiment confidence, clarity of the bull/bear debate resolution.
    Low conviction (2–4): conflicting signals, weak evidence.
    Medium conviction (5–7): moderate agreement, some uncertainty.
    High conviction (8–10): strong multi-source agreement, clear direction.

- expected_return: float, annualised, typically in range −0.25 to +0.25
    Your best estimate of the stock's annualised return given all the evidence.
    Positive for BUY signals, negative for SELL signals.
    Scale with conviction — a weak BUY might be +0.03, a strong BUY might be +0.18.
    SELL signals should be negative (e.g. −0.05 to −0.20).
    HOLD signals should be close to zero (e.g. −0.03 to +0.03).

- interpretation_rationale: one concise sentence explaining your reasoning.

Return ONLY valid JSON, no prose, no markdown fences:
{"signal": "BUY"|"SELL"|"HOLD", "conviction_score": float, "expected_return": float, "interpretation_rationale": "..."}
"""


def _llm_interpret(
    ticker: str,
    synthesis: str,
    sentiment: dict[str, Any],
    tech: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Call the LLM to extract signal, conviction_score and expected_return from
    the qualitative research package.  Returns None on any failure so the
    caller can fall back to formulas.
    """
    model_name = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    api_key    = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    # Build a compact summary of the inputs — avoid sending massive raw dicts
    debate = sentiment.get("debate", {})
    tech_signals = [
        {"name": s.get("name"), "direction": s.get("direction"), "strength": round(s.get("strength", 0), 3)}
        for s in tech.get("signals", [])
    ]

    package = {
        "ticker": ticker,
        "synthesis": synthesis,
        "sentiment": {
            "score":      sentiment.get("sentiment_score", 0.0),
            "label":      sentiment.get("sentiment_label", "NEUTRAL"),
            "confidence": sentiment.get("confidence", 0.0),
            "bull_case":  debate.get("bull_case", ""),
            "bear_case":  debate.get("bear_case", ""),
            "resolution": debate.get("resolution", ""),
        },
        "tech_signals": tech_signals,
    }

    human_text = (
        f"Research package for {ticker}:\n\n"
        f"{json.dumps(package, indent=2)}\n\n"
        f"Return the JSON interpretation now."
    )

    try:
        llm = ChatGroq(model=model_name, temperature=0.0, api_key=api_key)
        response = llm.invoke([
            SystemMessage(content=_INTERPRETATION_SYSTEM),
            HumanMessage(content=human_text),
        ])
        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)

        # Validate required fields and types
        signal = str(result.get("signal", "")).upper()
        if signal not in ("BUY", "SELL", "HOLD"):
            raise ValueError(f"Invalid signal: {signal}")
        conviction = float(result["conviction_score"])
        exp_return = float(result["expected_return"])
        rationale  = str(result.get("interpretation_rationale", ""))

        # Clamp to valid ranges
        conviction = max(0.0, min(10.0, conviction))
        exp_return = max(_MIN_EXP_RETURN, min(_MAX_EXP_RETURN, exp_return))

        logger.info(
            f"[adapter] {ticker}: LLM → signal={signal} conviction={conviction:.1f} "
            f"exp_ret={exp_return:+.1%} | {rationale}"
        )
        return {"signal": signal, "conviction_score": conviction, "expected_return": exp_return}

    except Exception as exc:
        logger.warning(f"[adapter] {ticker}: LLM interpretation failed ({exc}), using formula fallback")
        return None


# ---------------------------------------------------------------------------
# Formula fallbacks  (used only if the LLM call fails)
# ---------------------------------------------------------------------------

def _formula_signal(tech: dict[str, Any], sentiment: dict[str, Any], synthesis: str) -> str:
    """Regex-based signal extraction from synthesis with technical+sentiment fallback."""
    if synthesis:
        for line in synthesis.splitlines():
            if "recommendation" in line.lower():
                text = line.lower()
                if "buy" in text or "strong buy" in text:
                    return "BUY"
                if "sell" in text or "avoid" in text or "reduce" in text:
                    return "SELL"
                if "hold" in text or "neutral" in text or "watch" in text:
                    return "HOLD"
        lower = synthesis.lower()
        buy_hits  = len(re.findall(r"\bbuy\b|\baccumulate\b|\boverweight\b", lower))
        sell_hits = len(re.findall(r"\bsell\b|\bavoid\b|\bunderweight\b|\breduce\b", lower))
        hold_hits = len(re.findall(r"\bhold\b|\bneutral\b|\bwatch\b", lower))
        most = max(buy_hits, sell_hits, hold_hits)
        if most > 0:
            if buy_hits  == most: return "BUY"
            if sell_hits == most: return "SELL"
            return "HOLD"

    signals = tech.get("signals", [])
    direction_map = {"bullish": 1, "neutral": 0, "bearish": -1}
    avg_dir = (
        sum(direction_map.get(s.get("direction", "neutral"), 0) * s.get("strength", 0.5) for s in signals)
        / len(signals) if signals else 0.0
    )
    combined = avg_dir * 0.6 + float(sentiment.get("sentiment_score", 0.0)) * 0.4
    if combined >  0.15: return "BUY"
    if combined < -0.15: return "SELL"
    return "HOLD"


def _formula_conviction(tech: dict[str, Any], sentiment: dict[str, Any]) -> float:
    signals = tech.get("signals", [])
    avg_strength = (sum(s.get("strength", 0.5) for s in signals) / len(signals)) if signals else 0.5
    sent_confidence = float(sentiment.get("confidence", 0.5))
    return round(((avg_strength + sent_confidence) / 2.0) * 10.0, 2)


def _formula_expected_return(tech: dict[str, Any], sentiment: dict[str, Any]) -> float:
    signals = tech.get("signals", [])
    direction_map = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
    avg_dir = (
        sum(direction_map.get(s.get("direction", "neutral"), 0.0) * s.get("strength", 0.5) for s in signals)
        / len(signals) if signals else 0.0
    )
    base = avg_dir * 0.20
    adjusted = base + float(sentiment.get("sentiment_score", 0.0)) * 0.05
    return float(max(_MIN_EXP_RETURN, min(_MAX_EXP_RETURN, adjusted)))


# ---------------------------------------------------------------------------
# Volatility  — always formula-based (requires real price data)
# ---------------------------------------------------------------------------

def _derive_volatility(tech: dict[str, Any]) -> float:
    """
    Derive annualised volatility from ATR or Bollinger Band width.
    This MUST remain formula-based — volatility is a statistical property
    of price data; an LLM must not estimate it.
    """
    ind = tech.get("indicators", {})
    values = ind.get("values", ind)

    try:
        close = float(values.get("close") or values.get("Close") or 0)
        atr   = float(values.get("atr")   or values.get("ATRr_14") or 0)
        if close > 0 and atr > 0:
            return round((atr / close) * math.sqrt(252), 4)
    except (TypeError, ValueError):
        pass

    try:
        close    = float(values.get("close")    or values.get("Close")      or 0)
        bb_upper = float(values.get("bb_upper") or values.get("BBU_20_2.0") or 0)
        bb_lower = float(values.get("bb_lower") or values.get("BBL_20_2.0") or 0)
        if close > 0 and bb_upper > bb_lower:
            half_width = (bb_upper - bb_lower) / 2.0
            return round((half_width / close) / math.sqrt(20) * math.sqrt(252), 4)
    except (TypeError, ValueError):
        pass

    return _DEFAULT_VOLATILITY


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_research_output(
    combined_results: dict[str, Any],
    current_weights: dict[str, float] | None = None,
) -> ResearchTeamOutput:
    """
    Convert the Trading-Agent pipeline output into a ResearchTeamOutput
    ready for the Trader Agent.

    For each ticker:
      - Calls the LLM to interpret signal / conviction / expected_return from
        the synthesis + sentiment debate + technical signals.
      - Falls back to deterministic formulas if the LLM call fails.
      - Always derives volatility from ATR / Bollinger Bands (formula only).

    Args:
        combined_results: Full dict from run_full_analysis().
        current_weights:  Optional existing portfolio weights {ticker: decimal}.
                          Defaults to 0.0 for all tickers (testing assumption).
                          Pass real weights during live/FYP portfolio testing so
                          the Trader Agent produces correct BUY/SELL deltas.

    Returns:
        ResearchTeamOutput with one StockRecommendation per ticker.
    """
    if current_weights is None:
        current_weights = {}

    ticker_results: dict[str, Any] = combined_results.get("results", {})
    recommendations = []

    for ticker, data in ticker_results.items():
        tech      = data.get("technical", {})
        sentiment = data.get("sentiment", {})
        synthesis = data.get("synthesis", "")

        # ── 1. LLM interpretation (signal + conviction + expected_return) ──
        llm_result = _llm_interpret(ticker, synthesis, sentiment, tech)

        if llm_result:
            signal     = llm_result["signal"]
            conviction = llm_result["conviction_score"]
            exp_return = llm_result["expected_return"]
        else:
            # Formula fallback
            signal     = _formula_signal(tech, sentiment, synthesis)
            conviction = _formula_conviction(tech, sentiment)
            exp_return = _formula_expected_return(tech, sentiment)
            logger.info(
                f"[adapter] {ticker}: formula → signal={signal} conviction={conviction:.1f} "
                f"exp_ret={exp_return:+.1%}"
            )

        # ── 2. Volatility — always formula ──
        volatility     = _derive_volatility(tech)
        current_weight = float(current_weights.get(ticker, 0.0))

        rec = StockRecommendation(
            ticker=ticker,
            signal=signal,
            conviction_score=conviction,
            expected_return=exp_return,
            volatility=max(volatility, 0.01),
            current_weight=current_weight,
        )
        recommendations.append(rec)

    return ResearchTeamOutput(recommendations=recommendations)
