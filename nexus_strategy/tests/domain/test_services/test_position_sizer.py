"""Tests for the PositionSizer Kelly Criterion implementation."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    CompositeRegime,
    MacroRegime,
    MicroRegime,
    MidRegime,
    SynthesizedRegime,
)
from nexus_strategy.domain.models.signal import SignalBundle
from nexus_strategy.domain.services.position_sizer import PositionSizer


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _make_composite_regime(synthesized: SynthesizedRegime) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=75,
        duration_candles=10,
        transition_probability=0.1,
        recommended_strategies=["momentum"],
        risk_multiplier=1.0,
        max_position_size=0.15,
        timestamp=datetime.utcnow(),
    )


def _make_market_state(
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_MODERATE_BULL,
    sentinel: dict | None = None,
) -> MarketState:
    if sentinel is None:
        sentinel = {"risk_score": 0}
    return MarketState(
        timestamp=datetime.utcnow(),
        indicators={},
        composite_indicators={},
        regime=_make_composite_regime(synthesized),
        previous_regime=_make_composite_regime(SynthesizedRegime.REGIME_MODERATE_BULL),
        regime_just_changed=False,
        sentinel=sentinel,
        sentinel_connected=True,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.0,
        btc_change_24h=0.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="bull",
        altcoin_season_index=50,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _make_signal_bundle(
    composite_score: int = 70,
    suggested_stake_multiplier: float = 1.0,
) -> SignalBundle:
    return SignalBundle(
        action="BUY",
        pair="BTC/USDT",
        composite_score=composite_score,
        consensus_count=3,
        consensus_total=4,
        source_signals=[],
        regime=SynthesizedRegime.REGIME_MODERATE_BULL,
        suggested_stake_multiplier=suggested_stake_multiplier,
        weighted_stop_loss=0.02,
        merged_take_profits=[],
        risk_rating="LOW",
        reasoning="test",
        sentinel_context={},
        expiry_candles=5,
        created_at=datetime.utcnow(),
    )


def _make_sizer() -> PositionSizer:
    config = MagicMock()
    return PositionSizer(config=config)


def _good_portfolio() -> dict:
    """Portfolio state that produces a comfortable half-Kelly fraction."""
    return {
        "win_rate": 0.6,
        "avg_win": 0.04,
        "avg_loss": 0.02,
        "current_drawdown_pct": 0,
        "max_correlation": 0,
    }


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #

class TestBasicKelly:
    def test_basic_kelly_calculation(self):
        """Verify half-Kelly produces a sensible non-zero size for good inputs."""
        sizer = _make_sizer()
        portfolio = _good_portfolio()
        signal = _make_signal_bundle(composite_score=80)
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        size = sizer.calculate_size(signal, market, portfolio)

        # With good inputs the size should be between 5 % and 15 %
        assert 0.05 <= size <= 0.15

    def test_zero_avg_win_returns_zero(self):
        """When avg_win is zero the Kelly formula is undefined → return 0.0."""
        sizer = _make_sizer()
        portfolio = {
            "win_rate": 0.6,
            "avg_win": 0.0,
            "avg_loss": 0.02,
            "current_drawdown_pct": 0,
            "max_correlation": 0,
        }
        signal = _make_signal_bundle(composite_score=80)
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        size = sizer.calculate_size(signal, market, portfolio)

        assert size == 0.0

    def test_default_portfolio_state(self):
        """Default portfolio values must still yield a valid (possibly zero) size."""
        sizer = _make_sizer()
        signal = _make_signal_bundle(composite_score=70)
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        # Should not raise and must be in valid range
        size = sizer.calculate_size(signal, market, {})

        assert size == 0.0 or 0.05 <= size <= 0.15


class TestRegimeMultiplier:
    def _size_for_regime(self, synthesized: SynthesizedRegime) -> float:
        sizer = _make_sizer()
        portfolio = _good_portfolio()
        signal = _make_signal_bundle(composite_score=80)
        market = _make_market_state(synthesized)
        return sizer.calculate_size(signal, market, portfolio)

    def _raw_regime_mult(self, synthesized: SynthesizedRegime) -> float:
        sizer = _make_sizer()
        return sizer._regime_multiplier(_make_market_state(synthesized))

    def test_regime_multiplier_strong_bull(self):
        mult = self._raw_regime_mult(SynthesizedRegime.REGIME_STRONG_BULL)
        assert mult == pytest.approx(1.2)

    def test_regime_multiplier_breakout_bull(self):
        mult = self._raw_regime_mult(SynthesizedRegime.REGIME_BREAKOUT_BULL)
        assert mult == pytest.approx(1.2)

    def test_regime_multiplier_euphoria(self):
        mult = self._raw_regime_mult(SynthesizedRegime.REGIME_EUPHORIA)
        assert mult == pytest.approx(1.2)

    def test_regime_multiplier_panic(self):
        mult = self._raw_regime_mult(SynthesizedRegime.REGIME_PANIC)
        assert mult == pytest.approx(0.2)

    def test_regime_multiplier_strong_bull_yields_higher_size(self):
        """STRONG_BULL should yield a higher (or equal) size than MODERATE_BULL."""
        size_strong = self._size_for_regime(SynthesizedRegime.REGIME_STRONG_BULL)
        size_moderate = self._size_for_regime(SynthesizedRegime.REGIME_MODERATE_BULL)
        assert size_strong >= size_moderate

    def test_regime_multiplier_panic_yields_lower_size(self):
        """PANIC should yield a lower (or equal) size than MODERATE_BULL."""
        size_panic = self._size_for_regime(SynthesizedRegime.REGIME_PANIC)
        size_moderate = self._size_for_regime(SynthesizedRegime.REGIME_MODERATE_BULL)
        assert size_panic <= size_moderate


class TestConfidenceMultiplier:
    def test_confidence_multiplier(self):
        """Higher composite_score should produce a proportionally larger size."""
        sizer = _make_sizer()
        portfolio = _good_portfolio()
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        signal_low = _make_signal_bundle(composite_score=40)
        signal_high = _make_signal_bundle(composite_score=80)

        size_low = sizer.calculate_size(signal_low, market, portfolio)
        size_high = sizer.calculate_size(signal_high, market, portfolio)

        # Higher confidence → larger size (or both might be 0 / 0.05 if clamped)
        assert size_high >= size_low


class TestConsensusMultiplier:
    def test_consensus_multiplier(self):
        """A higher suggested_stake_multiplier should yield a larger position size."""
        sizer = _make_sizer()
        portfolio = _good_portfolio()
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        signal_low = _make_signal_bundle(composite_score=70, suggested_stake_multiplier=0.5)
        signal_high = _make_signal_bundle(composite_score=70, suggested_stake_multiplier=1.5)

        size_low = sizer.calculate_size(signal_low, market, portfolio)
        size_high = sizer.calculate_size(signal_high, market, portfolio)

        assert size_high >= size_low


class TestDrawdownMultiplier:
    def test_drawdown_multiplier(self):
        """Higher drawdown should reduce position size."""
        sizer = _make_sizer()
        signal = _make_signal_bundle(composite_score=80)
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        portfolio_low_dd = {**_good_portfolio(), "current_drawdown_pct": 5}
        portfolio_high_dd = {**_good_portfolio(), "current_drawdown_pct": 30}

        size_low_dd = sizer.calculate_size(signal, market, portfolio_low_dd)
        size_high_dd = sizer.calculate_size(signal, market, portfolio_high_dd)

        assert size_low_dd >= size_high_dd

    def test_drawdown_mult_floor(self):
        """Drawdown multiplier must never drop below 0.1."""
        sizer = _make_sizer()
        portfolio = {**_good_portfolio(), "current_drawdown_pct": 200}
        market = _make_market_state()
        mult = sizer._drawdown_multiplier(portfolio)
        assert mult >= 0.1


class TestCorrelationMultiplier:
    def test_correlation_multiplier(self):
        """High max_correlation should reduce position size."""
        sizer = _make_sizer()
        signal = _make_signal_bundle(composite_score=80)
        market = _make_market_state(SynthesizedRegime.REGIME_MODERATE_BULL)

        portfolio_low_corr = {**_good_portfolio(), "max_correlation": 0.1}
        portfolio_high_corr = {**_good_portfolio(), "max_correlation": 0.9}

        size_low = sizer.calculate_size(signal, market, portfolio_low_corr)
        size_high = sizer.calculate_size(signal, market, portfolio_high_corr)

        assert size_low >= size_high

    def test_correlation_mult_floor(self):
        """Correlation multiplier must never drop below 0.3."""
        sizer = _make_sizer()
        portfolio = {**_good_portfolio(), "max_correlation": 1.0}
        mult = sizer._correlation_multiplier(portfolio)
        assert mult >= 0.3


class TestSentinelMultiplier:
    def test_sentinel_low_risk(self):
        """Risk score below 60 → sentinel multiplier of 1.0."""
        sizer = _make_sizer()
        market = _make_market_state(sentinel={"risk_score": 30})
        mult = sizer._sentinel_multiplier(market)
        assert mult == pytest.approx(1.0)

    def test_sentinel_medium_risk(self):
        """Risk score in [60, 79] → sentinel multiplier of 0.7."""
        sizer = _make_sizer()
        market = _make_market_state(sentinel={"risk_score": 70})
        mult = sizer._sentinel_multiplier(market)
        assert mult == pytest.approx(0.7)

    def test_sentinel_high_risk(self):
        """Risk score >= 80 → sentinel multiplier of 0.3."""
        sizer = _make_sizer()
        market = _make_market_state(sentinel={"risk_score": 85})
        mult = sizer._sentinel_multiplier(market)
        assert mult == pytest.approx(0.3)

    def test_sentinel_high_risk_end_to_end(self):
        """High sentinel risk score should meaningfully reduce the final size."""
        sizer = _make_sizer()
        portfolio = _good_portfolio()
        signal = _make_signal_bundle(composite_score=80)

        market_safe = _make_market_state(
            SynthesizedRegime.REGIME_MODERATE_BULL, sentinel={"risk_score": 20}
        )
        market_risky = _make_market_state(
            SynthesizedRegime.REGIME_MODERATE_BULL, sentinel={"risk_score": 90}
        )

        size_safe = sizer.calculate_size(signal, market_safe, portfolio)
        size_risky = sizer.calculate_size(signal, market_risky, portfolio)

        assert size_safe >= size_risky


class TestSizeLimits:
    def test_min_size_threshold(self):
        """Computed size below 5 % must return 0.0 (don't trade)."""
        sizer = _make_sizer()
        # Tiny win_rate to force a near-zero Kelly
        portfolio = {
            "win_rate": 0.01,
            "avg_win": 0.001,
            "avg_loss": 0.05,
            "current_drawdown_pct": 90,
            "max_correlation": 0.95,
        }
        signal = _make_signal_bundle(composite_score=5, suggested_stake_multiplier=0.1)
        market = _make_market_state(SynthesizedRegime.REGIME_PANIC)

        size = sizer.calculate_size(signal, market, portfolio)

        assert size == 0.0

    def test_max_size_capped_at_15pct(self):
        """Position size must never exceed 15 % regardless of inputs."""
        sizer = _make_sizer()
        portfolio = {
            "win_rate": 0.99,
            "avg_win": 0.5,
            "avg_loss": 0.001,
            "current_drawdown_pct": 0,
            "max_correlation": 0,
        }
        signal = _make_signal_bundle(composite_score=100, suggested_stake_multiplier=2.0)
        market = _make_market_state(
            SynthesizedRegime.REGIME_STRONG_BULL, sentinel={"risk_score": 0}
        )

        size = sizer.calculate_size(signal, market, portfolio)

        assert size <= 0.15
