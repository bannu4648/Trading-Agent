"""
Global rate limiting for Mistral API (free tier: ~1 req/s and ~30 req/min).

Blocks before each chat invoke/stream until limits allow another request.
Disable with MISTRAL_THROTTLE=false. Tune with MISTRAL_MIN_INTERVAL_SEC and
MISTRAL_MAX_PER_MINUTE (leave headroom under your plan's cap).
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque

_lock = threading.Lock()
_last_start: float = 0.0
_window: Deque[float] = deque()
_env_loaded = False


def _load_env_once() -> None:
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        _env_loaded = True
        return
    root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / "backend" / ".env", override=False)
    _env_loaded = True


def mistral_throttle_enabled() -> bool:
    _load_env_once()
    v = (os.getenv("MISTRAL_THROTTLE") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _min_interval_sec() -> float:
    return float(os.getenv("MISTRAL_MIN_INTERVAL_SEC", "1.05"))


def _max_per_minute() -> int:
    return int(os.getenv("MISTRAL_MAX_PER_MINUTE", "28"))


def acquire_mistral_throttle() -> None:
    """Block until a new Mistral request may start (respects spacing + rolling minute)."""
    if not mistral_throttle_enabled():
        return
    global _last_start
    min_iv = _min_interval_sec()
    max_pm = _max_per_minute()
    window_sec = 60.0
    with _lock:
        while True:
            now = time.time()
            while _window and now - _window[0] >= window_sec:
                _window.popleft()
            if len(_window) >= max_pm:
                sleep_t = window_sec - (now - _window[0]) + 0.05
                _lock.release()
                try:
                    if sleep_t > 0:
                        time.sleep(sleep_t)
                finally:
                    _lock.acquire()
                continue
            now = time.time()
            if _last_start > 0:
                wait_iv = min_iv - (now - _last_start)
                if wait_iv > 0:
                    _lock.release()
                    try:
                        time.sleep(wait_iv)
                    finally:
                        _lock.acquire()
                    continue
            _last_start = time.time()
            _window.append(_last_start)
            return


def wrap_mistral_chat(model: Any) -> Any:
    """Return a thin wrapper that acquires the throttle before invoke/stream."""
    if not mistral_throttle_enabled():
        return model
    return _ThrottledChatMistralAI(model)


class _ThrottledChatMistralAI:
    """Delegates to ChatMistralAI; throttles invoke/stream (and common bind helpers)."""

    __slots__ = ("_inner",)

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        acquire_mistral_throttle()
        return self._inner.invoke(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        acquire_mistral_throttle()
        return self._inner.stream(*args, **kwargs)

    def bind_tools(self, *args: Any, **kwargs: Any) -> Any:
        bound = self._inner.bind_tools(*args, **kwargs)
        return wrap_mistral_chat(bound)

    def with_structured_output(self, *args: Any, **kwargs: Any) -> Any:
        out = self._inner.with_structured_output(*args, **kwargs)
        return wrap_mistral_chat(out)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
