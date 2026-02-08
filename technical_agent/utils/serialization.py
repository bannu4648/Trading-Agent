"""Helpers for JSON-safe serialization."""

from __future__ import annotations

import dataclasses
import json
import math
from typing import Any

import numpy as np
import pandas as pd


def to_serializable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (np.integer, np.floating)):
        item = value.item()
        if isinstance(item, float) and (math.isnan(item) or math.isinf(item)):
            return None
        return item
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, (pd.Series,)):
        return to_serializable(value.to_dict())
    if isinstance(value, (pd.DataFrame,)):
        return to_serializable(value.to_dict(orient="records"))
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(v) for v in value]
    return value


def dumps_json(data: Any, indent: int | None = 2) -> str:
    return json.dumps(data, default=to_serializable, indent=indent)
