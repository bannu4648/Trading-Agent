"""Langfuse tracing helpers for graph, tools, and LLM calls."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

from ..config import TracingConfig


@dataclass
class SpanHandle:
    """Safe wrapper around a Langfuse span/generation object."""

    observation: Any | None = None

    def update(
        self,
        *,
        input_data: Any | None = None,
        output_data: Any | None = None,
        level: str | None = None,
    ) -> None:
        if self.observation is None:
            return
        payload: Dict[str, Any] = {}
        if input_data is not None:
            payload["input"] = input_data
        if output_data is not None:
            payload["output"] = output_data
        if level is not None:
            payload["level"] = level
        if not payload:
            return
        try:
            self.observation.update(**payload)
        except Exception:
            pass

    def set_output(self, output_data: Any) -> None:
        self.update(output_data=output_data)

    def set_level(self, level: str) -> None:
        self.update(level=level)


@dataclass
class TraceRuntime:
    enabled: bool
    callbacks: List[Any] = field(default_factory=list)
    langfuse_client: Any | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def langchain_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        if self.callbacks:
            config["callbacks"] = self.callbacks
        if self.metadata:
            config["metadata"] = self.metadata
        return config

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input_data: Any | None = None,
        output_data: Any | None = None,
        level: str = "DEFAULT",
    ) -> Iterator[SpanHandle]:
        if not self.enabled or self.langfuse_client is None:
            yield SpanHandle()
            return

        try:
            with self.langfuse_client.start_as_current_span(
                name=name,
                input=input_data,
                output=output_data,
                level=level,
            ) as span:
                yield SpanHandle(span)
        except Exception:
            # Tracing failures must never break agent execution.
            yield SpanHandle()

    def flush(self) -> None:
        if not self.enabled or self.langfuse_client is None:
            return
        try:
            self.langfuse_client.flush()
        except Exception:
            pass


def _env_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _is_tracing_enabled(config: TracingConfig) -> bool:
    has_credentials = bool(
        _env_or_none(config.public_key) and _env_or_none(config.secret_key)
    )
    if config.enabled:
        return has_credentials
    return has_credentials


def build_trace_runtime(
    config: TracingConfig,
    *,
    run_name: str,
    request: Dict[str, Any],
) -> TraceRuntime:
    if not _is_tracing_enabled(config):
        return TraceRuntime(enabled=False)

    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler
    except Exception:
        return TraceRuntime(enabled=False)

    if config.host:
        os.environ["LANGFUSE_HOST"] = config.host
        os.environ["LANGFUSE_BASE_URL"] = config.host
    if config.public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = config.public_key
    if config.secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = config.secret_key

    try:
        client = get_client()
        callback_handler = CallbackHandler()
    except Exception:
        return TraceRuntime(enabled=False)

    tags: List[str] = [config.project_name] if config.project_name else []
    interval = request.get("interval")
    if interval:
        tags.append(f"interval:{interval}")

    metadata: Dict[str, Any] = {"run_name": run_name}
    if config.release:
        metadata["release"] = config.release
    if config.session_id:
        metadata["session_id"] = config.session_id
    if config.user_id:
        metadata["user_id"] = config.user_id

    if tags:
        metadata["tags"] = tags

    return TraceRuntime(
        enabled=True,
        callbacks=[callback_handler],
        langfuse_client=client,
        metadata=metadata,
    )
