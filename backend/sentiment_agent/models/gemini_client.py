"""
LLM client for sentiment subgraphs. Uses :mod:`llm_provider.resolve_llm` so that
missing cloud API keys transparently fall back to local Ollama (same as the rest
of the backend). Imports keep the name ``gemini_client`` for backward
compatibility.

When a stream emitter is installed (see :mod:`streaming_context`), token chunks
are forwarded for live UI (SSE).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, List, Optional

from streaming_context import emit_llm_chunk, emit_llm_end, emit_llm_start

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a financial sentiment analyst. "
    "Always respond with valid JSON when asked."
)


def _normalize_lc_chunk_content(chunk: object) -> str:
    c = getattr(chunk, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: List[str] = []
        for part in c:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                t = getattr(part, "text", None)
                parts.append(str(t) if t else "")
        return "".join(parts)
    return str(c)


class LLMClient:
    """Lazy-init LLM; provider comes from shared resolver (with Ollama fallback)."""

    def __init__(self) -> None:
        self._ready = False
        self.provider: str = "pending"
        self._resolved: Any = None
        self._oai: Any = None
        self._oai_model: Optional[str] = None
        self._ollama_chat: Any = None
        self._mistral_chat: Any = None
        self._gemini_client: Any = None
        self._gemini_model: Optional[str] = None
        self._anthropic_chat: Any = None

    def _ensure_initialized(self) -> None:
        if self._ready:
            return

        from llm_provider import resolve_llm

        r = resolve_llm()
        self._resolved = r
        self.provider = r.provider
        logger.info(f"Initializing sentiment LLM client with provider: {self.provider}")

        if r.provider == "ollama":
            from langchain_ollama import ChatOllama

            self._ollama_chat = ChatOllama(
                model=r.model,
                base_url=r.ollama_base_url,
                temperature=0.3,
            )
        elif r.provider == "mistral":
            from langchain_mistralai import ChatMistralAI

            mkw: dict[str, Any] = {
                "model": r.model,
                "api_key": r.api_key,
                "temperature": 0.3,
            }
            m_endpoint = (os.getenv("MISTRAL_API_BASE_URL") or "").strip()
            if m_endpoint:
                mkw["endpoint"] = m_endpoint.rstrip("/")
            from llm_provider.mistral_throttle import wrap_mistral_chat

            self._mistral_chat = wrap_mistral_chat(ChatMistralAI(**mkw))
        elif r.provider in ("groq", "deepseek", "openai"):
            from openai import OpenAI

            base = r.openai_compatible_base_url
            if not base:
                base = "https://api.openai.com/v1"
            self._oai = OpenAI(api_key=r.api_key, base_url=base)
            self._oai_model = r.model
        elif r.provider == "gemini":
            from google import genai

            if not r.api_key:
                raise ValueError("GEMINI_API_KEY is required when using Gemini.")
            self._gemini_client = genai.Client(api_key=r.api_key)
            self._gemini_model = r.model
        elif r.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            self._anthropic_chat = ChatAnthropic(
                model=r.model,
                api_key=r.api_key,
                temperature=0.3,
            )
        else:
            raise ValueError(f"Unsupported LLM provider for sentiment: {self.provider}")

        self._ready = True

    def generate(
        self,
        prompt: str,
        max_retries: int = 4,
        *,
        stream_pipeline: str = "sentiment",
    ) -> str:
        self._ensure_initialized()
        logger.info(
            "[llm] sentiment.generate provider=%s prompt_chars=%s pipeline=%s",
            self.provider,
            len(prompt),
            stream_pipeline,
        )
        if self.provider == "ollama":
            return self._generate_ollama(prompt, max_retries, stream_pipeline)
        if self.provider == "mistral":
            return self._generate_mistral(prompt, max_retries, stream_pipeline)
        if self.provider == "gemini":
            return self._generate_gemini(prompt, max_retries, stream_pipeline)
        if self.provider == "anthropic":
            return self._generate_anthropic(prompt, max_retries, stream_pipeline)
        return self._generate_openai_compatible(prompt, max_retries, stream_pipeline)

    def generate_json(self, prompt: str, max_retries: int = 4) -> dict:
        raw = self.generate(prompt, max_retries=max_retries, stream_pipeline="sentiment")
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {raw[:500]}")
            raise ValueError(f"Invalid JSON from {self.provider}: {e}") from e

    def _generate_ollama(self, prompt: str, max_retries: int, pl: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        delay = 2.0
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ]
        for attempt in range(max_retries):
            try:
                emit_llm_start(pipeline=pl, agent="ollama", ticker=None)
                acc: List[str] = []
                try:
                    for chunk in self._ollama_chat.stream(messages):
                        piece = _normalize_lc_chunk_content(chunk)
                        if piece:
                            acc.append(piece)
                            emit_llm_chunk(
                                pipeline=pl,
                                agent="ollama",
                                chunk=piece,
                            )
                    text = "".join(acc).strip()
                except Exception:
                    resp = self._ollama_chat.invoke(messages)
                    text = (resp.content or "").strip()
                emit_llm_end(pipeline=pl, agent="ollama", ticker=None)
                return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        logger.warning(
                            f"Ollama rate/backoff (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"Ollama error: {e}")
                raise

    def _generate_mistral(self, prompt: str, max_retries: int, pl: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        delay = 5.0
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ]
        for attempt in range(max_retries):
            try:
                emit_llm_start(pipeline=pl, agent="mistral", ticker=None)
                acc: List[str] = []
                try:
                    for chunk in self._mistral_chat.stream(messages):
                        piece = _normalize_lc_chunk_content(chunk)
                        if piece:
                            acc.append(piece)
                            emit_llm_chunk(
                                pipeline=pl,
                                agent="mistral",
                                chunk=piece,
                            )
                    text = "".join(acc).strip()
                except Exception:
                    resp = self._mistral_chat.invoke(messages)
                    text = (resp.content or "").strip()
                emit_llm_end(pipeline=pl, agent="mistral", ticker=None)
                return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        logger.warning(
                            "Mistral rate/backoff (attempt %s/%s). Waiting %ss...",
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        time.sleep(wait)
                        continue
                logger.error("Mistral API error: %s", e)
                raise

    def _generate_anthropic(self, prompt: str, max_retries: int, pl: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        delay = 5.0
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ]
        for attempt in range(max_retries):
            try:
                emit_llm_start(pipeline=pl, agent="anthropic", ticker=None)
                acc: List[str] = []
                try:
                    for chunk in self._anthropic_chat.stream(messages):
                        piece = _normalize_lc_chunk_content(chunk)
                        if piece:
                            acc.append(piece)
                            emit_llm_chunk(
                                pipeline=pl,
                                agent="anthropic",
                                chunk=piece,
                            )
                    text = "".join(acc).strip()
                except Exception:
                    resp = self._anthropic_chat.invoke(messages)
                    text = (resp.content or "").strip()
                emit_llm_end(pipeline=pl, agent="anthropic", ticker=None)
                return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        logger.warning(
                            f"Rate limit (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"Anthropic API error: {e}")
                raise

    def _generate_gemini(self, prompt: str, max_retries: int, pl: str) -> str:
        delay = 15
        for attempt in range(max_retries):
            try:
                emit_llm_start(pipeline=pl, agent="gemini", ticker=None)
                acc: List[str] = []
                used_stream = False
                try:
                    stream_fn = getattr(
                        self._gemini_client.models, "generate_content_stream", None
                    )
                    if stream_fn is None:
                        raise AttributeError("no generate_content_stream")
                    for part in stream_fn(
                        model=self._gemini_model,
                        contents=prompt,
                    ):
                        used_stream = True
                        t = getattr(part, "text", None) or ""
                        if t:
                            acc.append(t)
                            emit_llm_chunk(
                                pipeline=pl,
                                agent="gemini",
                                chunk=t,
                            )
                except Exception as stream_err:
                    logger.debug(
                        "Gemini stream skipped (%s); using generate_content",
                        stream_err,
                    )
                    used_stream = False

                if used_stream and acc:
                    text = "".join(acc).strip()
                else:
                    response = self._gemini_client.models.generate_content(
                        model=self._gemini_model,
                        contents=prompt,
                    )
                    text = response.text.strip()
                    if text:
                        emit_llm_chunk(
                            pipeline=pl,
                            agent="gemini",
                            chunk=text,
                        )
                emit_llm_end(pipeline=pl, agent="gemini", ticker=None)
                return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        logger.warning(
                            f"Rate limit hit (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"Gemini API error: {e}")
                raise

    def _generate_openai_compatible(self, prompt: str, max_retries: int, pl: str) -> str:
        delay = 5
        for attempt in range(max_retries):
            try:
                emit_llm_start(pipeline=pl, agent=self.provider, ticker=None)
                acc: List[str] = []
                try:
                    stream = self._oai.chat.completions.create(
                        model=self._oai_model,
                        messages=[
                            {"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,
                        stream=True,
                    )
                    for chunk in stream:
                        delta = ""
                        if chunk.choices:
                            d = chunk.choices[0].delta
                            if d is not None:
                                delta = getattr(d, "content", None) or ""
                        if delta:
                            acc.append(delta)
                            emit_llm_chunk(
                                pipeline=pl,
                                agent=self.provider,
                                chunk=delta,
                            )
                    text = "".join(acc).strip()
                except Exception:
                    response = self._oai.chat.completions.create(
                        model=self._oai_model,
                        messages=[
                            {"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,
                    )
                    text = (response.choices[0].message.content or "").strip()
                    if text:
                        emit_llm_chunk(
                            pipeline=pl,
                            agent=self.provider,
                            chunk=text,
                        )
                emit_llm_end(pipeline=pl, agent=self.provider, ticker=None)
                return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        logger.warning(
                            f"Rate limit hit (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"{self.provider} API error: {e}")
                raise


gemini_client = LLMClient()
