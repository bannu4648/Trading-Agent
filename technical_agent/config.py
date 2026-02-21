"""Configuration for the technical analyst agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional fallback for non-uv runs
    def load_dotenv(*args, **kwargs):  # type: ignore[no-redef]
        return False

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    ichimoku_tenkan: int = 9
    ichimoku_kijun: int = 26
    ichimoku_senkou: int = 52
    supertrend_period: int = 10
    supertrend_multiplier: float = 3.0
    donchian_length: int = 20
    keltner_length: int = 20
    keltner_scalar: float = 2.0
    psar_step: float = 0.02
    psar_max_step: float = 0.2
    pivot_lookback: int = 1
    vwap_enabled: bool = True
    intraday_overrides: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "1m": {
                "sma_periods": [10, 20, 50],
                "ema_periods": [8, 21],
                "rsi_period": 9,
                "macd_fast": 6,
                "macd_slow": 13,
                "macd_signal": 5,
                "bb_length": 20,
                "bb_std": 2.0,
            },
            "5m": {
                "sma_periods": [10, 20, 50],
                "ema_periods": [8, 21],
                "rsi_period": 10,
                "macd_fast": 8,
                "macd_slow": 21,
                "macd_signal": 5,
            },
            "15m": {
                "sma_periods": [20, 50, 100],
                "ema_periods": [12, 26],
                "rsi_period": 12,
            },
            "30m": {
                "sma_periods": [20, 50, 100],
                "ema_periods": [12, 26],
                "rsi_period": 12,
            },
            "1h": {
                "sma_periods": [20, 50, 100],
                "ema_periods": [12, 26],
                "rsi_period": 14,
            },
        }
    )

    def for_interval(self, interval: str) -> "IndicatorConfig":
        interval_key = interval.lower()
        overrides = self.intraday_overrides.get(interval_key)
        if not overrides and interval_key.endswith("m"):
            overrides = self.intraday_overrides.get("5m")
        if not overrides and interval_key.endswith("h"):
            overrides = self.intraday_overrides.get("1h")

        if not overrides:
            return self

        data = {**self.__dict__}
        data.update(overrides)
        return IndicatorConfig(**data)


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
class TracingConfig:
    enabled: bool = False
    project_name: str = "technical-agent"
    host: str | None = None
    public_key: str | None = None
    secret_key: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    release: str | None = None


@dataclass
class AgentConfig:
    data: DataConfig = field(default_factory=DataConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    extra_signal_modules: List[str] = field(default_factory=list)
    enable_llm_summary: bool = True


def config_from_env() -> AgentConfig:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    def _env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    # pick the right model name and API key for the chosen provider
    if provider == "ollama":
        llm_model = os.getenv("OLLAMA_MODEL")
        llm_api_key = None
    elif provider == "groq":
        llm_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm_api_key = os.getenv("GROQ_API_KEY")
    else:  # gemini / google
        llm_model = os.getenv("GEMINI_MODEL")
        llm_api_key = os.getenv("GEMINI_API_KEY")

    llm_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    llm_config = LLMConfig(
        provider=provider,
        model=llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
    )

    tracing_config = TracingConfig(
        enabled=_env_bool("LANGFUSE_ENABLED", False),
        project_name=os.getenv("LANGFUSE_PROJECT", "technical-agent"),
        host=os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        user_id=os.getenv("LANGFUSE_USER_ID"),
        session_id=os.getenv("LANGFUSE_SESSION_ID"),
        release=os.getenv("LANGFUSE_RELEASE"),
    )

    return AgentConfig(llm=llm_config, tracing=tracing_config)
