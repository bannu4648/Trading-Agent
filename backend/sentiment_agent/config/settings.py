"""
Loads configuration from .env using pydantic-settings.

LLM routing for sentiment is handled by ``llm_provider.resolve_llm`` (shared
with other agents): cloud keys when present, otherwise Ollama. Finnhub and
weight settings below still apply.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Legacy field; sentiment uses llm_provider.resolve_llm instead.
    llm_provider: str = "auto"

    # API keys (only need the one for whichever provider you picked)
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # Finnhub API key for analyst data (free at https://finnhub.io/register)
    finnhub_api_key: Optional[str] = "d7d77khr01qggoen8ccgd7d77khr01qggoen8cd0"

    # model names with reasonable defaults
    groq_model: str = "llama-3.3-70b-versatile"
    deepseek_model: str = "deepseek-chat"
    gemini_model: str = "gemini-2.0-flash"

    # Research-backed weights (Change 4 — IEEE/arXiv 2024-25):
    # Analyst consensus from Finnhub = most reliable (institutional data from dozens of analysts)
    # News = second most reliable (primary source events)
    # Social = noisier (Reddit volume ≠ sentiment quality)
    # Web = reduced to near-zero: DuckDuckGo scraper consistently returns 0.0 scores
    #       giving it high weight actively hurts accuracy (drags down confidence)
    weight_news: float = 0.35
    weight_social: float = 0.15
    weight_analyst: float = 0.40
    weight_web: float = 0.10

    # If True, a web score of exactly 0.0 is treated as missing (not counted)
    # and its weight is redistributed to the other sources
    web_zero_means_missing: bool = True

    # Skip social + web + debate LLM steps (news + analyst + aggregate + summary only).
    # Env: SENTIMENT_FAST_PIPELINE=true
    sentiment_fast_pipeline: bool = False

    # Analyst confidence floor: if analyst_score >= this, confidence >= analyst_floor
    analyst_confidence_threshold: float = 0.7
    analyst_confidence_floor: float = 0.55


settings = Settings()
