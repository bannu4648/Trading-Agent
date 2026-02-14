"""Template for custom signal extensions.

Add new signals here or create separate modules and register them via
AgentConfig.extra_signal_modules.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from ..config import SignalConfig
from ..models import Signal
from .registry import register_signal


@register_signal("example_custom_signal", "Example placeholder for future expansion.")
def example_custom_signal(
    symbol: str, df: pd.DataFrame, config: SignalConfig
) -> List[Signal]:
    # Replace this with your own logic.
    return []
