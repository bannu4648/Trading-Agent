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

# Repo root (parent of backend/) so .env at project root is loaded
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


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
    rsi_period: int = 14          # primary RSI period (academic standard)
    rsi_period_short: int = 9     # secondary RSI for short-term momentum (Change 1)
    lookback_days: int = 200      # min data history for stable RSI-14 (was 60 — bug fix)
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
    # Adaptive thresholds: research shows 75/25 better for volatile tech stocks
    # (vs classic 70/30 which generates too many false signals in trending markets)
    rsi_overbought: float = 75.0
    rsi_oversold: float = 25.0
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
    """Groq / DeepSeek OpenAI-compatible API base URL when applicable."""
    openai_base_url: str | None = None


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
    load_dotenv(REPO_ROOT / ".env", override=False)

    def _env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    from llm_provider import resolve_llm

    resolved = resolve_llm()
    provider = resolved.provider
    llm_model = resolved.model
    llm_api_key = resolved.api_key
    llm_base_url = resolved.ollama_base_url
    openai_compat = resolved.openai_compatible_base_url
    if provider == "mistral":
        m_base = os.getenv("MISTRAL_API_BASE_URL")
        if m_base and m_base.strip():
            openai_compat = m_base.strip().rstrip("/")

    llm_config = LLMConfig(
        provider=provider,
        model=llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key,
        openai_base_url=openai_compat,
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
