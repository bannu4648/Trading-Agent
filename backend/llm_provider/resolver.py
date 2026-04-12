"""
Central LLM resolution for the Trading-Agent backend.

Chooses a concrete provider and model from environment variables. When a cloud
provider is requested but its API key is missing, falls back to local Ollama
so the full pipeline runs without keys (local dev). In UAT/production, set
keys and optionally LLM_PROVIDER to use hosted models.

Resolution rules (after loading .env from repo root and backend/.env):
- LLM_PROVIDER unset or empty or "auto": pick the first available in order
  Mistral → Groq → Gemini → DeepSeek → OpenAI → Anthropic → Ollama.
- LLM_PROVIDER set to a specific provider: use it only if the required key
  exists; otherwise fall back to Ollama with an info log.
- LLM_PROVIDER=ollama: always Ollama (local).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

ProviderName = Literal[
    "ollama", "mistral", "groq", "gemini", "deepseek", "openai", "anthropic"
]

_dotenv_loaded = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _ensure_dotenv_loaded() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        _dotenv_loaded = True
        return
    root = _repo_root()
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / "backend" / ".env", override=False)
    _dotenv_loaded = True


def _strip_key(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    s = v.strip()
    return s or None


@dataclass(frozen=True)
class ResolvedLLM:
    """Effective LLM backend after applying fallback rules."""

    provider: ProviderName
    model: str
    api_key: Optional[str]
    ollama_base_url: str
    """OpenAI-compatible base URL for Groq or DeepSeek; unused for other providers."""
    openai_compatible_base_url: Optional[str] = None


def _gemini_key() -> Optional[str]:
    return _strip_key("GEMINI_API_KEY") or _strip_key("GOOGLE_API_KEY")


def _pick_auto_provider() -> ProviderName:
    if _strip_key("MISTRAL_API_KEY"):
        return "mistral"
    if _strip_key("GROQ_API_KEY"):
        return "groq"
    if _gemini_key():
        return "gemini"
    if _strip_key("DEEPSEEK_API_KEY"):
        return "deepseek"
    if _strip_key("OPENAI_API_KEY"):
        return "openai"
    if _strip_key("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama"


def _model_for(provider: ProviderName) -> str:
    defaults = {
        "ollama": os.getenv("OLLAMA_MODEL") or "qwen3.5:9b",
        "mistral": os.getenv("MISTRAL_MODEL") or "mistral-large-latest",
        "groq": os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile",
        "gemini": os.getenv("GEMINI_MODEL") or "gemini-2.0-flash",
        "deepseek": os.getenv("DEEPSEEK_MODEL") or "deepseek-chat",
        "openai": os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        "anthropic": os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022",
    }
    return defaults[provider]


def resolve_llm() -> ResolvedLLM:
    """
    Return the effective LLM configuration for this process.

    Call after env is ready; loads .env once from standard locations.
    """
    _ensure_dotenv_loaded()

    raw = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

    if raw in ("", "auto"):
        p = _pick_auto_provider()
        if p == "ollama":
            logger.info(
                "[llm_provider] No cloud API keys found; using Ollama (%s)",
                _model_for("ollama"),
            )
        else:
            logger.info("[llm_provider] Auto-selected provider: %s", p)
        return ResolvedLLM(
            provider=p,
            model=_model_for(p),
            api_key=_api_key_for(p),
            ollama_base_url=ollama_url,
            openai_compatible_base_url=_openai_url_for(p),
        )

    if raw == "ollama":
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw == "mistral":
        key = _strip_key("MISTRAL_API_KEY")
        if key:
            return ResolvedLLM(
                provider="mistral",
                model=_model_for("mistral"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url=None,
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=mistral but MISTRAL_API_KEY missing; "
            "falling back to Ollama"
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw in ("google", "gemini"):
        key = _gemini_key()
        if key:
            return ResolvedLLM(
                provider="gemini",
                model=_model_for("gemini"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url=None,
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=%s but no GEMINI/GOOGLE key; falling back to Ollama",
            raw,
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw == "groq":
        key = _strip_key("GROQ_API_KEY")
        if key:
            return ResolvedLLM(
                provider="groq",
                model=_model_for("groq"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url="https://api.groq.com/openai/v1",
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=groq but GROQ_API_KEY missing; falling back to Ollama"
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw == "deepseek":
        key = _strip_key("DEEPSEEK_API_KEY")
        if key:
            return ResolvedLLM(
                provider="deepseek",
                model=_model_for("deepseek"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url="https://api.deepseek.com",
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY missing; "
            "falling back to Ollama"
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw == "openai":
        key = _strip_key("OPENAI_API_KEY")
        if key:
            return ResolvedLLM(
                provider="openai",
                model=_model_for("openai"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url="https://api.openai.com/v1",
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=openai but OPENAI_API_KEY missing; falling back to Ollama"
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    if raw in ("anthropic", "claude"):
        key = _strip_key("ANTHROPIC_API_KEY")
        if key:
            return ResolvedLLM(
                provider="anthropic",
                model=_model_for("anthropic"),
                api_key=key,
                ollama_base_url=ollama_url,
                openai_compatible_base_url=None,
            )
        logger.info(
            "[llm_provider] LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY missing; "
            "falling back to Ollama"
        )
        return ResolvedLLM(
            provider="ollama",
            model=_model_for("ollama"),
            api_key=None,
            ollama_base_url=ollama_url,
            openai_compatible_base_url=None,
        )

    logger.warning(
        "[llm_provider] Unknown LLM_PROVIDER=%r; falling back to Ollama", raw
    )
    return ResolvedLLM(
        provider="ollama",
        model=_model_for("ollama"),
        api_key=None,
        ollama_base_url=ollama_url,
        openai_compatible_base_url=None,
    )


def _api_key_for(provider: ProviderName) -> Optional[str]:
    if provider == "mistral":
        return _strip_key("MISTRAL_API_KEY")
    if provider == "groq":
        return _strip_key("GROQ_API_KEY")
    if provider == "gemini":
        return _gemini_key()
    if provider == "deepseek":
        return _strip_key("DEEPSEEK_API_KEY")
    if provider == "openai":
        return _strip_key("OPENAI_API_KEY")
    if provider == "anthropic":
        return _strip_key("ANTHROPIC_API_KEY")
    return None


def _openai_url_for(provider: ProviderName) -> Optional[str]:
    if provider == "groq":
        return "https://api.groq.com/openai/v1"
    if provider == "deepseek":
        return "https://api.deepseek.com"
    if provider == "openai":
        return "https://api.openai.com/v1"
    return None


def get_langchain_chat_model(
    *,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    forward_sse: bool = False,
    sse_pipeline: str = "langchain",
    sse_agent: str = "chat",
    wrap_observed: bool = True,
) -> Any:
    """
    Build a LangChain chat model matching :func:`resolve_llm`.

    Used by the trader agent, adapter interpretation, and fundamentals helper.

    Set ``forward_sse=True`` (and optional ``sse_pipeline`` / ``sse_agent``) to
    mirror model output to the job SSE stream for the live UI.

    Set ``wrap_observed=False`` when passing the model to LangGraph helpers such
    as ``create_react_agent``: they compose ``prompt | model`` and require a
    :class:`~langchain_core.runnables.Runnable` chat model. In that mode the
    observability wrapper is skipped, and for Mistral the rate-limit throttle
    wrapper is also skipped (it is not Runnable-compatible either).
    """
    r = resolve_llm()
    inner: Any

    if r.provider == "ollama":
        from langchain_ollama import ChatOllama

        inner = ChatOllama(
            model=r.model,
            base_url=r.ollama_base_url,
            temperature=temperature,
        )

    elif r.provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        kwargs: dict[str, Any] = {
            "model": r.model,
            "api_key": r.api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        endpoint = _strip_key("MISTRAL_API_BASE_URL")
        if endpoint:
            kwargs["endpoint"] = endpoint.rstrip("/")
        base_mistral = ChatMistralAI(**kwargs)
        if wrap_observed:
            from llm_provider.mistral_throttle import wrap_mistral_chat

            inner = wrap_mistral_chat(base_mistral)
        else:
            inner = base_mistral

    elif r.provider == "groq":
        from langchain_groq import ChatGroq

        inner = ChatGroq(
            model=r.model,
            temperature=temperature,
            api_key=r.api_key,
        )

    elif r.provider == "deepseek":
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": r.model,
            "api_key": r.api_key,
            "base_url": r.openai_compatible_base_url,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        inner = ChatOpenAI(**kwargs)

    elif r.provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": r.model,
            "api_key": r.api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        inner = ChatOpenAI(**kwargs)

    elif r.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = {
            "model": r.model,
            "api_key": r.api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        inner = ChatAnthropic(**kwargs)

    elif r.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        kwargs = {
            "model": r.model,
            "google_api_key": r.api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        inner = ChatGoogleGenerativeAI(**kwargs)

    else:
        raise ValueError(f"Unsupported provider: {r.provider}")

    if not wrap_observed:
        return inner

    from llm_provider.observed_chat import wrap_observed_chat

    return wrap_observed_chat(
        inner,
        source="get_langchain_chat_model",
        provider=r.provider,
        model=r.model,
        forward_sse=forward_sse,
        sse_pipeline=sse_pipeline,
        sse_agent=sse_agent,
    )
