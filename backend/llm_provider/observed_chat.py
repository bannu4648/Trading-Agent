"""
Wrap LangChain chat models to log every invoke/stream and optionally mirror
token chunks to :mod:`streaming_context` (SSE → frontend).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterator, List

from streaming_context import emit_llm_chunk, emit_llm_end, emit_llm_start

logger = logging.getLogger("llm.call")


def _llm_observability_enabled() -> bool:
    v = (os.getenv("LLM_CALL_LOG") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _normalize_stream_chunk_content(chunk: object) -> str:
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


def _approx_messages_chars(messages: object) -> int:
    if messages is None:
        return 0
    if not isinstance(messages, list):
        return 0
    n = 0
    for m in messages:
        c = getattr(m, "content", None)
        if isinstance(c, str):
            n += len(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict):
                    n += len(str(part.get("text", "")))
                else:
                    n += len(str(getattr(part, "text", part)))
    return n


def _response_content_len(response: object) -> int:
    c = getattr(response, "content", None)
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return len(_normalize_stream_chunk_content(response))
    return len(str(c)) if c is not None else 0


def wrap_observed_chat(
    inner: Any,
    *,
    source: str,
    provider: str,
    model: str,
    forward_sse: bool = False,
    sse_pipeline: str = "langchain",
    sse_agent: str = "chat",
) -> Any:
    """Decorate a chat model; preserves bind_tools / with_structured_output chains."""
    return _ObservedChatModel(
        inner,
        {
            "source": source,
            "provider": provider,
            "model": model,
            "forward_sse": forward_sse,
            "sse_pipeline": sse_pipeline,
            "sse_agent": sse_agent,
        },
    )


class _ObservedChatModel:
    __slots__ = ("_inner", "_opts")

    def __init__(self, inner: Any, opts: Dict[str, Any]) -> None:
        self._inner = inner
        self._opts = opts

    def _chain(self, inner: Any) -> _ObservedChatModel:
        return _ObservedChatModel(inner, self._opts)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        log_en = _llm_observability_enabled()
        messages = args[0] if args else kwargs.get("input") or kwargs.get("messages")
        inch = _approx_messages_chars(messages)
        t0 = time.perf_counter()
        src = self._opts["source"]
        prov = self._opts["provider"]
        mod = self._opts["model"]
        if log_en:
            logger.info(
                "[llm] invoke_start source=%s provider=%s model=%s input_chars=%s",
                src,
                prov,
                mod,
                inch,
            )

        out = self._inner.invoke(*args, **kwargs)

        dt_ms = (time.perf_counter() - t0) * 1000
        olen = _response_content_len(out)
        if log_en:
            logger.info(
                "[llm] invoke_end source=%s provider=%s model=%s duration_ms=%.1f output_chars=%s",
                src,
                prov,
                mod,
                dt_ms,
                olen,
            )

        if self._opts.get("forward_sse"):
            piece = _normalize_stream_chunk_content(out)
            emit_llm_start(
                pipeline=self._opts["sse_pipeline"],
                agent=self._opts["sse_agent"],
                ticker=None,
            )
            if piece:
                emit_llm_chunk(
                    pipeline=self._opts["sse_pipeline"],
                    agent=self._opts["sse_agent"],
                    ticker=None,
                    chunk=piece,
                )
            emit_llm_end(
                pipeline=self._opts["sse_pipeline"],
                agent=self._opts["sse_agent"],
                ticker=None,
            )

        return out

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        log_en = _llm_observability_enabled()
        messages = args[0] if args else kwargs.get("input") or kwargs.get("messages")
        inch = _approx_messages_chars(messages)
        src = self._opts["source"]
        prov = self._opts["provider"]
        mod = self._opts["model"]
        if log_en:
            logger.info(
                "[llm] stream_start source=%s provider=%s model=%s input_chars=%s",
                src,
                prov,
                mod,
                inch,
            )

        raw_it = self._inner.stream(*args, **kwargs)
        forward = self._opts.get("forward_sse")

        def _gen() -> Iterator[Any]:
            t0 = time.perf_counter()
            n_chunks = 0
            n_chars = 0
            if forward:
                emit_llm_start(
                    pipeline=self._opts["sse_pipeline"],
                    agent=self._opts["sse_agent"],
                    ticker=None,
                )
            try:
                for chunk in raw_it:
                    n_chunks += 1
                    piece = _normalize_stream_chunk_content(chunk)
                    if piece:
                        n_chars += len(piece)
                    if forward and piece:
                        emit_llm_chunk(
                            pipeline=self._opts["sse_pipeline"],
                            agent=self._opts["sse_agent"],
                            ticker=None,
                            chunk=piece,
                        )
                    yield chunk
            finally:
                if forward:
                    emit_llm_end(
                        pipeline=self._opts["sse_pipeline"],
                        agent=self._opts["sse_agent"],
                        ticker=None,
                    )
                if log_en:
                    logger.info(
                        "[llm] stream_end source=%s provider=%s model=%s duration_ms=%.1f "
                        "chunks=%s streamed_chars=%s",
                        src,
                        prov,
                        mod,
                        (time.perf_counter() - t0) * 1000,
                        n_chunks,
                        n_chars,
                    )

        return _gen()

    def bind_tools(self, *args: Any, **kwargs: Any) -> Any:
        bound = self._inner.bind_tools(*args, **kwargs)
        return self._chain(bound)

    def with_structured_output(self, *args: Any, **kwargs: Any) -> Any:
        out = self._inner.with_structured_output(*args, **kwargs)
        return self._chain(out)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
