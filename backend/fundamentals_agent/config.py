"""
Configuration for the Fundamentals Agent.
"""
import os
from typing import Any, Dict


DEFAULT_CONFIG = {
    # LLM settings — actual provider resolved via llm_provider (Ollama fallback)
    "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
    "model": os.getenv("LLM_MODEL", "llama3.2"),
    "temperature": 0.7,
    "max_tokens": 4000,
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "max_iterations": 5,
    "vendor": os.getenv("DATA_VENDOR", "yfinance"),
    "debug": False,
}


def get_llm_client(config: Dict[str, Any] | None = None):
    """
    LangChain chat model from shared resolver (cloud keys → hosted; else Ollama).
    """
    if config is None:
        config = {}
    from llm_provider import get_langchain_chat_model

    temperature = float(config.get("temperature", DEFAULT_CONFIG["temperature"]))
    max_tokens = int(config.get("max_tokens", DEFAULT_CONFIG["max_tokens"]))
    return get_langchain_chat_model(temperature=temperature, max_tokens=max_tokens)
