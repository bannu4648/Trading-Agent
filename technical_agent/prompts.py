"""Prompt templates for LLM-driven summaries."""

TECHNICAL_SUMMARY_SYSTEM_PROMPT = """You are a technical analyst in a trading team.
Use only the provided indicators and signals.
Do not invent prices, news, or fundamentals.
Explain the technical posture in 3-6 sentences.
Be precise about uncertainty when signals conflict."""


def build_summary_prompt(symbol: str, indicator_snapshot_json: str, signals_json: str) -> str:
    return (
        "Symbol: {symbol}\n"
        "Latest indicator snapshot (JSON):\n{indicator_snapshot}\n\n"
        "Signals (JSON):\n{signals}\n\n"
        "Summarize the current technical posture and key risks."
    ).format(
        symbol=symbol,
        indicator_snapshot=indicator_snapshot_json,
        signals=signals_json,
    )
