"""Tests for MarketState domain model."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
)
from nexus_strategy.domain.models.market_state import (
    MarketState,
    SENTINEL_STALE_THRESHOLD_SECONDS,
)


def _make_composite_regime():
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=SynthesizedRegime.REGIME_STRONG_BULL,
        confidence=85,
        duration_candles=20,
        transition_probability=0.1,
        recommended_strategies=["momentum"],
        risk_multiplier=1.0,
        max_position_size=0.05,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _make_market_state(**kwargs):
    regime = _make_composite_regime()
    defaults = dict(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        indicators={"BTC/USDT": {"1h": {"rsi": 65.0, "macd": 0.5}}},
        composite_indicators={"BTC/USDT": {"trend_score": 0.8}},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=True,
        sentinel_data_age_seconds=100,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=2.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="markup",
        altcoin_season_index=60,
        fear_greed=70,
        indicator_weights={"rsi": 0.3, "macd": 0.3},
        strategy_weights={"momentum": {"weight": 0.5}},
        indicator_reliability={"rsi": 0.9},
    )
    defaults.update(kwargs)
    return MarketState(**defaults)


class TestSentinelStaleThreshold:
    def test_constant_value(self):
        assert SENTINEL_STALE_THRESHOLD_SECONDS == 300

    def test_constant_is_int(self):
        assert isinstance(SENTINEL_STALE_THRESHOLD_SECONDS, int)


class TestMarketStateIsFrozen:
    def test_is_frozen(self):
        ms = _make_market_state()
        with pytest.raises((AttributeError, TypeError)):
            ms.btc_price = 99999.0  # type: ignore


class TestSentinelIsStale:
    def test_not_stale_below_threshold(self):
        ms = _make_market_state(sentinel_data_age_seconds=299)
        assert ms.sentinel_is_stale is False

    def test_not_stale_at_threshold(self):
        ms = _make_market_state(sentinel_data_age_seconds=300)
        assert ms.sentinel_is_stale is False

    def test_stale_above_threshold(self):
        ms = _make_market_state(sentinel_data_age_seconds=301)
        assert ms.sentinel_is_stale is True

    def test_stale_well_above_threshold(self):
        ms = _make_market_state(sentinel_data_age_seconds=1000)
        assert ms.sentinel_is_stale is True


class TestGetIndicator:
    def test_get_existing_indicator(self):
        ms = _make_market_state(
            indicators={"BTC/USDT": {"1h": {"rsi": 65.0}}}
        )
        result = ms.get_indicator("BTC/USDT", "1h", "rsi")
        assert result == 65.0

    def test_get_nonexistent_pair_returns_none(self):
        ms = _make_market_state(
            indicators={"BTC/USDT": {"1h": {"rsi": 65.0}}}
        )
        result = ms.get_indicator("ETH/USDT", "1h", "rsi")
        assert result is None

    def test_get_nonexistent_timeframe_returns_none(self):
        ms = _make_market_state(
            indicators={"BTC/USDT": {"1h": {"rsi": 65.0}}}
        )
        result = ms.get_indicator("BTC/USDT", "4h", "rsi")
        assert result is None

    def test_get_nonexistent_indicator_returns_none(self):
        ms = _make_market_state(
            indicators={"BTC/USDT": {"1h": {"rsi": 65.0}}}
        )
        result = ms.get_indicator("BTC/USDT", "1h", "stoch")
        assert result is None

    def test_get_indicator_multiple_pairs(self):
        ms = _make_market_state(
            indicators={
                "BTC/USDT": {"1h": {"rsi": 65.0}},
                "ETH/USDT": {"1h": {"rsi": 45.0}},
            }
        )
        assert ms.get_indicator("BTC/USDT", "1h", "rsi") == 65.0
        assert ms.get_indicator("ETH/USDT", "1h", "rsi") == 45.0


class TestMarketStateFields:
    def test_basic_fields(self):
        ms = _make_market_state()
        assert ms.btc_price == 50000.0
        assert ms.sentinel_connected is True
        assert ms.btc_above_ema200 is True
        assert ms.btc_trend == "bullish"
        assert ms.market_phase == "markup"
        assert ms.altcoin_season_index == 60
        assert ms.fear_greed == 70

    def test_regime_is_composite_regime(self):
        ms = _make_market_state()
        assert isinstance(ms.regime, CompositeRegime)
