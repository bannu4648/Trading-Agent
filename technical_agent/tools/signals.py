"""Signal generation tool using the registry."""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from ..config import SignalConfig
from ..models import Signal
from ..signals.registry import (
    get_registered_signals,
    load_builtin_signals,
    load_extra_signals,
)
from ..utils.serialization import to_serializable


def generate_signals(
    indicator_data: Dict[str, pd.DataFrame],
    config: SignalConfig,
    extra_modules: List[str] | None = None,
) -> Tuple[Dict[str, List[dict]], List[str]]:
    load_builtin_signals()
    if extra_modules:
        load_extra_signals(extra_modules)

    errors: List[str] = []
    result: Dict[str, List[dict]] = {}

    for symbol, df in indicator_data.items():
        symbol_signals: List[dict] = []
        for definition in get_registered_signals():
            try:
                signals: List[Signal] = definition.func(symbol, df, config)
                for signal in signals:
                    data = signal.to_dict() if hasattr(signal, "to_dict") else signal
                    data = to_serializable(data)
                    symbol_signals.append(data)
            except Exception as exc:
                errors.append(f"{symbol}:{definition.name}:{exc}")
        result[symbol] = symbol_signals

    return result, errors
