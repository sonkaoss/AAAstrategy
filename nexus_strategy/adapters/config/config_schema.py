"""Pydantic config validation schema — Task 11."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GeneralConfig(BaseModel):
    max_open_trades: int = Field(default=10, ge=1, le=30)
    base_timeframe: str = Field(default="5m")
    informative_timeframes: list[str] = Field(default=["15m", "1h", "4h", "1d"])
    profile: str = Field(default="balanced")
    min_confidence: int = Field(default=45, ge=0, le=100)
    min_consensus: int = Field(default=2, ge=1, le=7)
    dry_run: bool = Field(default=True)


class RiskConfig(BaseModel):
    max_exposure: float = Field(default=0.85, ge=0.0, le=1.0)
    max_single_pair: float = Field(default=0.20, ge=0.01, le=0.50)
    max_sector: float = Field(default=0.35, ge=0.05, le=0.60)
    min_sectors: int = Field(default=3, ge=1)
    max_correlation: float = Field(default=0.85, ge=0.0, le=1.0)
    kelly_fraction: float = Field(default=0.50, ge=0.05, le=1.0)
    drawdown_caution: float = Field(default=0.05, ge=0.01, le=0.20)
    drawdown_warning: float = Field(default=0.10, ge=0.03, le=0.30)
    drawdown_critical: float = Field(default=0.15, ge=0.05, le=0.40)
    drawdown_catastrophic: float = Field(default=0.20, ge=0.10, le=0.50)


class RegimeConfig(BaseModel):
    transition_min_candles: int = Field(default=3, ge=1, le=20)
    panic_instant_transition: bool = Field(default=True)
    high_confidence_threshold: int = Field(default=70, ge=50, le=95)
    markov_lookback_candles: int = Field(default=2016, ge=288, le=8640)


class StrategyWeightsConfig(BaseModel):
    mean_reversion: float = Field(default=1.0, ge=0.0, le=3.0)
    trend_following: float = Field(default=1.0, ge=0.0, le=3.0)
    momentum_breakout: float = Field(default=1.0, ge=0.0, le=3.0)
    volatility_squeeze: float = Field(default=1.0, ge=0.0, le=3.0)
    volume_profile: float = Field(default=1.0, ge=0.0, le=3.0)
    divergence: float = Field(default=1.0, ge=0.0, le=3.0)
    market_structure: float = Field(default=1.0, ge=0.0, le=3.0)


class DCAConfig(BaseModel):
    enabled: bool = Field(default=True)
    max_dca_count: int = Field(default=4, ge=0, le=10)
    min_dca_interval_candles: int = Field(default=6, ge=1, le=48)
    require_technical_confirmation: bool = Field(default=True)


class ExitConfig(BaseModel):
    emergency_drop_pct: float = Field(default=0.10, ge=0.03, le=0.25)
    doom_stop_default: float = Field(default=0.08, ge=0.03, le=0.20)
    portfolio_total_loss_limit: float = Field(default=0.20, ge=0.10, le=0.40)
    trailing_atr_multiplier: float = Field(default=2.5, ge=1.0, le=5.0)
    time_decay_enabled: bool = Field(default=True)
    time_decay_rate_per_6h: float = Field(default=0.10, ge=0.0, le=0.25)
    max_time_decay: float = Field(default=0.50, ge=0.10, le=0.80)


class SentinelConfig(BaseModel):
    enabled: bool = Field(default=True)
    redis_url: str = Field(default="redis://localhost:6379/0")
    fallback_json_path: str = Field(default="sentinel_data.json")
    stale_threshold_seconds: int = Field(default=300, ge=30, le=600)
    risk_shutdown_threshold: int = Field(default=90, ge=50, le=100)
    risk_defensive_threshold: int = Field(default=80, ge=40, le=95)


class LearningConfig(BaseModel):
    enabled: bool = Field(default=True)
    min_trades_for_learning: int = Field(default=20, ge=5, le=100)
    base_learning_rate: float = Field(default=0.01, ge=0.001, le=0.10)
    max_parameter_drift: float = Field(default=0.50, ge=0.10, le=1.0)
    cooldown_candles: int = Field(default=288, ge=12, le=2016)
    backtest_learning: bool = Field(default=False)


class AnalyticsConfig(BaseModel):
    decision_logging: bool = Field(default=True)
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)
    trade_journal_enabled: bool = Field(default=True)
    daily_report: bool = Field(default=True)
    weekly_report: bool = Field(default=True)


class NexusConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    strategy_weights: StrategyWeightsConfig = Field(default_factory=StrategyWeightsConfig)
    dca: DCAConfig = Field(default_factory=DCAConfig)
    exit: ExitConfig = Field(default_factory=ExitConfig)
    sentinel: SentinelConfig = Field(default_factory=SentinelConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
