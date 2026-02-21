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

    # how much weight each agent gets in the final score (should sum to 1.0)
    # analyst data is the most reliable signal (institutional consensus from
    # dozens of analysts), followed by news headlines. Social and web are
    # noisier -- social measures volume not sentiment, and web scraping is
    # inconsistent across runs.
    weight_news: float = 0.30
    weight_social: float = 0.15
    weight_analyst: float = 0.35
    weight_web: float = 0.20


settings = Settings()
