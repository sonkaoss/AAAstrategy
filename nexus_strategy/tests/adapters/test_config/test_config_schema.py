"""Tests for Pydantic config schema — Task 11."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_schema():
    from nexus_strategy.adapters.config.config_schema import (
        GeneralConfig,
        RiskConfig,
        RegimeConfig,
        StrategyWeightsConfig,
        DCAConfig,
        ExitConfig,
        SentinelConfig,
        LearningConfig,
        AnalyticsConfig,
        NexusConfig,
    )
    return (
        GeneralConfig, RiskConfig, RegimeConfig, StrategyWeightsConfig,
        DCAConfig, ExitConfig, SentinelConfig, LearningConfig,
        AnalyticsConfig, NexusConfig,
    )


# ---------------------------------------------------------------------------
# GeneralConfig
# ---------------------------------------------------------------------------

class TestGeneralConfig:
    def test_defaults(self):
        (GeneralConfig, *_) = _import_schema()
        cfg = GeneralConfig()
        assert cfg.max_open_trades == 10
        assert cfg.base_timeframe == "5m"
        assert cfg.informative_timeframes == ["15m", "1h", "4h", "1d"]
        assert cfg.profile == "balanced"
        assert cfg.min_confidence == 45
        assert cfg.min_consensus == 2
        assert cfg.dry_run is True

    def test_custom_values(self):
        (GeneralConfig, *_) = _import_schema()
        cfg = GeneralConfig(max_open_trades=5, profile="conservative", dry_run=False)
        assert cfg.max_open_trades == 5
        assert cfg.profile == "conservative"
        assert cfg.dry_run is False

    def test_max_open_trades_too_low(self):
        (GeneralConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            GeneralConfig(max_open_trades=0)

    def test_max_open_trades_too_high(self):
        (GeneralConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            GeneralConfig(max_open_trades=31)

    def test_min_confidence_out_of_range(self):
        (GeneralConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            GeneralConfig(min_confidence=101)

    def test_min_consensus_too_high(self):
        (GeneralConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            GeneralConfig(min_consensus=8)


# ---------------------------------------------------------------------------
# RiskConfig
# ---------------------------------------------------------------------------

class TestRiskConfig:
    def test_defaults(self):
        (_, RiskConfig, *_) = _import_schema()
        cfg = RiskConfig()
        assert cfg.max_exposure == pytest.approx(0.85)
        assert cfg.max_single_pair == pytest.approx(0.20)
        assert cfg.max_sector == pytest.approx(0.35)
        assert cfg.min_sectors == 3
        assert cfg.max_correlation == pytest.approx(0.85)
        assert cfg.kelly_fraction == pytest.approx(0.50)
        assert cfg.drawdown_caution == pytest.approx(0.05)
        assert cfg.drawdown_warning == pytest.approx(0.10)
        assert cfg.drawdown_critical == pytest.approx(0.15)
        assert cfg.drawdown_catastrophic == pytest.approx(0.20)

    def test_max_exposure_out_of_range(self):
        (_, RiskConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            RiskConfig(max_exposure=1.1)

    def test_kelly_fraction_too_low(self):
        (_, RiskConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            RiskConfig(kelly_fraction=0.04)

    def test_min_sectors_too_low(self):
        (_, RiskConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            RiskConfig(min_sectors=0)


# ---------------------------------------------------------------------------
# RegimeConfig
# ---------------------------------------------------------------------------

class TestRegimeConfig:
    def test_defaults(self):
        (_, _, RegimeConfig, *_) = _import_schema()
        cfg = RegimeConfig()
        assert cfg.transition_min_candles == 3
        assert cfg.panic_instant_transition is True
        assert cfg.high_confidence_threshold == 70
        assert cfg.markov_lookback_candles == 2016

    def test_transition_too_many_candles(self):
        (_, _, RegimeConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            RegimeConfig(transition_min_candles=21)

    def test_high_confidence_too_low(self):
        (_, _, RegimeConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            RegimeConfig(high_confidence_threshold=49)


# ---------------------------------------------------------------------------
# StrategyWeightsConfig
# ---------------------------------------------------------------------------

class TestStrategyWeightsConfig:
    def test_defaults(self):
        (_, _, _, StrategyWeightsConfig, *_) = _import_schema()
        cfg = StrategyWeightsConfig()
        assert cfg.mean_reversion == pytest.approx(1.0)
        assert cfg.trend_following == pytest.approx(1.0)
        assert cfg.momentum_breakout == pytest.approx(1.0)
        assert cfg.volatility_squeeze == pytest.approx(1.0)
        assert cfg.volume_profile == pytest.approx(1.0)
        assert cfg.divergence == pytest.approx(1.0)
        assert cfg.market_structure == pytest.approx(1.0)

    def test_weight_out_of_range(self):
        (_, _, _, StrategyWeightsConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            StrategyWeightsConfig(mean_reversion=3.1)

    def test_weight_negative(self):
        (_, _, _, StrategyWeightsConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            StrategyWeightsConfig(trend_following=-0.1)


# ---------------------------------------------------------------------------
# DCAConfig
# ---------------------------------------------------------------------------

class TestDCAConfig:
    def test_defaults(self):
        (_, _, _, _, DCAConfig, *_) = _import_schema()
        cfg = DCAConfig()
        assert cfg.enabled is True
        assert cfg.max_dca_count == 4
        assert cfg.min_dca_interval_candles == 6
        assert cfg.require_technical_confirmation is True

    def test_max_dca_count_out_of_range(self):
        (_, _, _, _, DCAConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            DCAConfig(max_dca_count=11)


# ---------------------------------------------------------------------------
# ExitConfig
# ---------------------------------------------------------------------------

class TestExitConfig:
    def test_defaults(self):
        (_, _, _, _, _, ExitConfig, *_) = _import_schema()
        cfg = ExitConfig()
        assert cfg.emergency_drop_pct == pytest.approx(0.10)
        assert cfg.doom_stop_default == pytest.approx(0.08)
        assert cfg.portfolio_total_loss_limit == pytest.approx(0.20)
        assert cfg.trailing_atr_multiplier == pytest.approx(2.5)
        assert cfg.time_decay_enabled is True
        assert cfg.time_decay_rate_per_6h == pytest.approx(0.10)
        assert cfg.max_time_decay == pytest.approx(0.50)

    def test_emergency_drop_too_low(self):
        (_, _, _, _, _, ExitConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            ExitConfig(emergency_drop_pct=0.02)

    def test_trailing_atr_too_high(self):
        (_, _, _, _, _, ExitConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            ExitConfig(trailing_atr_multiplier=5.1)


# ---------------------------------------------------------------------------
# SentinelConfig
# ---------------------------------------------------------------------------

class TestSentinelConfig:
    def test_defaults(self):
        (_, _, _, _, _, _, SentinelConfig, *_) = _import_schema()
        cfg = SentinelConfig()
        assert cfg.enabled is True
        assert cfg.redis_url == "redis://localhost:6379/0"
        assert cfg.fallback_json_path == "sentinel_data.json"
        assert cfg.stale_threshold_seconds == 300
        assert cfg.risk_shutdown_threshold == 90
        assert cfg.risk_defensive_threshold == 80

    def test_stale_threshold_too_low(self):
        (_, _, _, _, _, _, SentinelConfig, *_) = _import_schema()
        with pytest.raises(ValidationError):
            SentinelConfig(stale_threshold_seconds=29)


# ---------------------------------------------------------------------------
# LearningConfig
# ---------------------------------------------------------------------------

class TestLearningConfig:
    def test_defaults(self):
        from nexus_strategy.adapters.config.config_schema import LearningConfig
        cfg = LearningConfig()
        assert cfg.enabled is True
        assert cfg.min_trades_for_learning == 20
        assert cfg.base_learning_rate == pytest.approx(0.01)
        assert cfg.max_parameter_drift == pytest.approx(0.50)
        assert cfg.cooldown_candles == 288
        assert cfg.backtest_learning is False

    def test_base_learning_rate_too_high(self):
        from nexus_strategy.adapters.config.config_schema import LearningConfig
        with pytest.raises(ValidationError):
            LearningConfig(base_learning_rate=0.11)


# ---------------------------------------------------------------------------
# AnalyticsConfig
# ---------------------------------------------------------------------------

class TestAnalyticsConfig:
    def test_defaults(self):
        (*_, AnalyticsConfig, _) = _import_schema()
        cfg = AnalyticsConfig()
        assert cfg.decision_logging is True
        assert cfg.prometheus_enabled is True
        assert cfg.prometheus_port == 9090
        assert cfg.trade_journal_enabled is True
        assert cfg.daily_report is True
        assert cfg.weekly_report is True

    def test_prometheus_port_out_of_range(self):
        (*_, AnalyticsConfig, _) = _import_schema()
        with pytest.raises(ValidationError):
            AnalyticsConfig(prometheus_port=1023)


# ---------------------------------------------------------------------------
# NexusConfig (composite)
# ---------------------------------------------------------------------------

class TestNexusConfig:
    def test_full_defaults(self):
        (*_, NexusConfig) = _import_schema()
        cfg = NexusConfig()
        assert cfg.general.max_open_trades == 10
        assert cfg.risk.max_exposure == pytest.approx(0.85)
        assert cfg.regime.transition_min_candles == 3
        assert cfg.strategy_weights.mean_reversion == pytest.approx(1.0)
        assert cfg.dca.enabled is True
        assert cfg.exit.doom_stop_default == pytest.approx(0.08)
        assert cfg.sentinel.enabled is True
        assert cfg.learning.enabled is True
        assert cfg.analytics.prometheus_port == 9090

    def test_from_dict_partial_override(self):
        (*_, NexusConfig) = _import_schema()
        data = {
            "general": {"max_open_trades": 5, "profile": "conservative"},
            "risk": {"kelly_fraction": 0.30},
        }
        cfg = NexusConfig(**data)
        assert cfg.general.max_open_trades == 5
        assert cfg.general.profile == "conservative"
        assert cfg.risk.kelly_fraction == pytest.approx(0.30)
        # non-overridden fields keep defaults
        assert cfg.general.min_confidence == 45
        assert cfg.dca.enabled is True

    def test_invalid_nested_raises(self):
        (*_, NexusConfig) = _import_schema()
        with pytest.raises(ValidationError):
            NexusConfig(general={"max_open_trades": 999})
