"""Backward-compatible serialization imports.

Prefer importing from `technical_agent.shared.serialization`.
"""

from ..shared.serialization import dumps_json, to_serializable

__all__ = ["dumps_json", "to_serializable"]
