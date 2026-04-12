"""
Thread-local streaming hooks for LLM token events.

The FastAPI analysis job runs in a worker thread and installs an emitter
that pushes dicts into a queue; SSE reads that queue. All sync pipeline code
in the same thread calls :func:`emit_stream_event` / :func:`emit_llm_chunk`.
"""
from __future__ import annotations

import contextvars
import logging
import time
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List, Optional

_sse_log = logging.getLogger("llm.stream")
# Per (pipeline, agent, ticker) stack of perf_counter() at llm_start for duration on llm_end
_start_times: DefaultDict[str, List[float]] = defaultdict(list)

StreamEmitter = Callable[[Dict[str, Any]], None]

_emitter: contextvars.ContextVar[Optional[StreamEmitter]] = contextvars.ContextVar(
    "stream_emitter", default=None
)

# Optional ticker for subgraphs that don't receive ticker in the LLM helper (e.g. sentiment).
_stream_ticker: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "stream_ticker", default=None
)


def set_stream_emitter(fn: Optional[StreamEmitter]) -> contextvars.Token:
    return _emitter.set(fn)


def reset_stream_emitter(token: contextvars.Token) -> None:
    _emitter.reset(token)


def set_stream_ticker(ticker: Optional[str]) -> contextvars.Token:
    return _stream_ticker.set(ticker)


def reset_stream_ticker(token: contextvars.Token) -> None:
    _stream_ticker.reset(token)


def get_stream_ticker() -> Optional[str]:
    return _stream_ticker.get()


def _sse_track_key(pipeline: str, agent: str, ticker: Optional[str]) -> str:
    return f"{pipeline}\0{agent}\0{ticker or ''}"


def emit_stream_event(event: Dict[str, Any]) -> None:
    fn = _emitter.get()
    if fn is None:
        return
    try:
        fn(event)
    except Exception:
        pass


def emit_llm_chunk(
    *,
    pipeline: str,
    agent: str,
    chunk: str,
    ticker: Optional[str] = None,
) -> None:
    if not chunk:
        return
    tid = ticker if ticker is not None else get_stream_ticker()
    emit_stream_event(
        {
            "type": "llm_chunk",
            "pipeline": pipeline,
            "agent": agent,
            "ticker": tid,
            "chunk": chunk,
        }
    )


def emit_llm_start(
    *,
    pipeline: str,
    agent: str,
    ticker: Optional[str] = None,
) -> None:
    tid = ticker if ticker is not None else get_stream_ticker()
    key = _sse_track_key(pipeline, agent, tid)
    _start_times[key].append(time.perf_counter())
    _sse_log.info(
        "[llm] sse_token_stream_start pipeline=%s agent=%s ticker=%s",
        pipeline,
        agent,
        tid or "-",
    )
    emit_stream_event(
        {
            "type": "llm_start",
            "pipeline": pipeline,
            "agent": agent,
            "ticker": tid,
        }
    )


def emit_llm_end(
    *,
    pipeline: str,
    agent: str,
    ticker: Optional[str] = None,
) -> None:
    tid = ticker if ticker is not None else get_stream_ticker()
    key = _sse_track_key(pipeline, agent, tid)
    stack = _start_times.get(key)
    duration_ms: Optional[float] = None
    if stack:
        t0 = stack.pop()
        duration_ms = (time.perf_counter() - t0) * 1000
        if not stack:
            del _start_times[key]
    if duration_ms is not None:
        _sse_log.info(
            "[llm] sse_token_stream_end pipeline=%s agent=%s ticker=%s duration_ms=%.1f",
            pipeline,
            agent,
            tid or "-",
            duration_ms,
        )
    else:
        _sse_log.info(
            "[llm] sse_token_stream_end pipeline=%s agent=%s ticker=%s",
            pipeline,
            agent,
            tid or "-",
        )
    emit_stream_event(
        {
            "type": "llm_end",
            "pipeline": pipeline,
            "agent": agent,
            "ticker": tid,
        }
    )


def emit_stage(*, pipeline: str, label: str, ticker: Optional[str] = None) -> None:
    tid = ticker if ticker is not None else get_stream_ticker()
    emit_stream_event(
        {
            "type": "stage",
            "pipeline": pipeline,
            "label": label,
            "ticker": tid,
        }
    )
