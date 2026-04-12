"""LLM provider factory for the technical agent."""

from __future__ import annotations

from typing import Any

from .config import LLMConfig


def _observe_technical(inner: Any, provider: str, model: str) -> Any:
    from llm_provider.observed_chat import wrap_observed_chat

    return wrap_observed_chat(
        inner,
        source="technical_agent",
        provider=provider,
        model=model,
        forward_sse=False,
        sse_pipeline="technical",
        sse_agent="summary_lc",
    )


def get_llm(llm_config: LLMConfig) -> Any:
    provider = (llm_config.provider or "ollama").lower()
    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-ollama. Install it to use Ollama."
            ) from exc

        model = llm_config.model or "qwen3.5:9b"
        return _observe_technical(
            ChatOllama(
                model=model,
                base_url=llm_config.base_url or "http://localhost:11434",
                temperature=llm_config.temperature,
            ),
            "ollama",
            model,
        )

    if provider == "mistral":
        try:
            from langchain_mistralai import ChatMistralAI
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-mistralai. Install it to use Mistral."
            ) from exc

        model = llm_config.model or "mistral-large-latest"
        if not llm_config.api_key:
            raise ValueError("MISTRAL_API_KEY is required for Mistral provider.")

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": llm_config.api_key,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        }
        if llm_config.openai_base_url:
            kwargs["endpoint"] = llm_config.openai_base_url.rstrip("/")
        from llm_provider.mistral_throttle import wrap_mistral_chat

        return _observe_technical(
            wrap_mistral_chat(ChatMistralAI(**kwargs)),
            "mistral",
            model,
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

        return _observe_technical(
            ChatGoogleGenerativeAI(
                model=model,
                google_api_key=llm_config.api_key,
                temperature=llm_config.temperature,
                max_output_tokens=llm_config.max_tokens,
            ),
            "gemini",
            model,
        )

    if provider == "groq":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-openai. Install it to use Groq."
            ) from exc

        model = llm_config.model or "llama-3.3-70b-versatile"
        if not llm_config.api_key:
            raise ValueError("GROQ_API_KEY is required for Groq provider.")

        return _observe_technical(
            ChatOpenAI(
                model=model,
                api_key=llm_config.api_key,
                base_url=llm_config.openai_base_url or "https://api.groq.com/openai/v1",
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            ),
            "groq",
            model,
        )

    if provider == "deepseek":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-openai. Install it to use DeepSeek."
            ) from exc

        model = llm_config.model or "deepseek-chat"
        if not llm_config.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek provider.")

        return _observe_technical(
            ChatOpenAI(
                model=model,
                api_key=llm_config.api_key,
                base_url=llm_config.openai_base_url or "https://api.deepseek.com",
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            ),
            "deepseek",
            model,
        )

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-openai. Install it to use OpenAI."
            ) from exc

        model = llm_config.model or "gpt-4o-mini"
        if not llm_config.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")

        return _observe_technical(
            ChatOpenAI(
                model=model,
                api_key=llm_config.api_key,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            ),
            "openai",
            model,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "Missing dependency langchain-anthropic. Install it to use Anthropic."
            ) from exc

        model = llm_config.model or "claude-3-5-sonnet-20241022"
        if not llm_config.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider.")

        return _observe_technical(
            ChatAnthropic(
                model=model,
                api_key=llm_config.api_key,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            ),
            "anthropic",
            model,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")

