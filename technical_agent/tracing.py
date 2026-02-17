"""Backward-compatible tracing imports.

Prefer importing from `technical_agent.observability.tracing`.
"""

from .observability.tracing import SpanHandle, TraceRuntime, build_trace_runtime

__all__ = ["SpanHandle", "TraceRuntime", "build_trace_runtime"]
