"""Configuration for the technical analyst agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class DataConfig:
    tickers: List[str] = field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    interval: str = "1d"
    auto_adjust: bool = True
    prepost: bool = False


@dataclass
class IndicatorConfig:
    sma_periods: List[int] = field(default_factory=lambda: [20, 50, 200])
    ema_periods: List[int] = field(default_factory=lambda: [12, 26])
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_length: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    adx_period: int = 14
    stoch_k: int = 14
    stoch_d: int = 3
    stoch_smooth: int = 3
    cci_period: int = 20
    roc_period: int = 12
    willr_period: int = 14
    mfi_period: int = 14
    volume_zscore_period: int = 20


@dataclass
class SignalConfig:
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    stoch_overbought: float = 80.0
    stoch_oversold: float = 20.0
    adx_trend_threshold: float = 25.0
    volume_zscore_threshold: float = 2.0
    min_strength: float = 0.0


@dataclass
class LLMConfig:
    provider: str = "ollama"
    temperature: float = 0.2
    max_tokens: int = 512
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@dataclass
class AgentConfig:
    data: DataConfig = field(default_factory=DataConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    extra_signal_modules: List[str] = field(default_factory=list)
    enable_llm_summary: bool = True


def config_from_env() -> AgentConfig:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    llm_model = os.getenv("OLLAMA_MODEL") if provider == "ollama" else os.getenv("GEMINI_MODEL")
    llm_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_api_key = os.getenv("GEMINI_API_KEY")

    llm_config = LLMConfig(
        provider=provider,
        model=llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
    )

    return AgentConfig(llm=llm_config)
