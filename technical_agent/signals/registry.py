"""Signal registry and plugin loader."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, Dict, List

import pandas as pd

from ..config import SignalConfig
from ..models import Signal


SignalFunction = Callable[[str, pd.DataFrame, SignalConfig], List[Signal]]


@dataclass
class SignalDefinition:
    name: str
    description: str
    func: SignalFunction


class SignalRegistry:
    def __init__(self) -> None:
        self._signals: Dict[str, SignalDefinition] = {}

    def register(self, name: str, description: str) -> Callable[[SignalFunction], SignalFunction]:
        def decorator(func: SignalFunction) -> SignalFunction:
            self._signals[name] = SignalDefinition(name=name, description=description, func=func)
            return func

        return decorator

    def list_signals(self) -> List[SignalDefinition]:
        return list(self._signals.values())


REGISTRY = SignalRegistry()


def register_signal(name: str, description: str) -> Callable[[SignalFunction], SignalFunction]:
    return REGISTRY.register(name, description)


def get_registered_signals() -> List[SignalDefinition]:
    return REGISTRY.list_signals()


def load_builtin_signals() -> None:
    importlib.import_module("technical_agent.signals.builtins")


def load_extra_signals(module_paths: List[str]) -> None:
    for module_path in module_paths:
        importlib.import_module(module_path)
