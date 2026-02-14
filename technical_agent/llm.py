"""LLM provider factory for the technical agent."""

from __future__ import annotations

from typing import Any

from .config import LLMConfig


def get_llm(llm_config: LLMConfig) -> Any:
    provider = (llm_config.provider or "ollama").lower()
    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-ollama. Install it to use Ollama."
            ) from exc

        model = llm_config.model or "llama3.1:8b"
        return ChatOllama(
            model=model,
            base_url=llm_config.base_url or "http://localhost:11434",
            temperature=llm_config.temperature,
        )

    if provider in {"gemini", "google"}:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-google-genai. Install it to use Gemini."
            ) from exc

        model = llm_config.model or "gemini-1.5-flash"
        if not llm_config.api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider.")

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=llm_config.api_key,
            temperature=llm_config.temperature,
            max_output_tokens=llm_config.max_tokens,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
