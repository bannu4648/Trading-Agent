"""
Loads configuration from .env file using pydantic-settings.
Supports switching between LLM providers (Groq, DeepSeek, Gemini)
via the LLM_PROVIDER environment variable.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # which LLM backend to use -- "groq", "deepseek", or "gemini"
    llm_provider: str = "groq"

    # API keys (only need the one for whichever provider you picked)
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # Finnhub API key for analyst data (free at https://finnhub.io/register)
    finnhub_api_key: Optional[str] = None

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

    # Analyst confidence floor: if analyst_score >= this, confidence >= analyst_floor
    analyst_confidence_threshold: float = 0.7
    analyst_confidence_floor: float = 0.55


settings = Settings()
