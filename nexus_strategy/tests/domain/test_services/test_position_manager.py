"""Tests for PositionManager — DCA, Derisk, and Buyback position management."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
)
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.services.position_manager import PositionManager


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

PAIR = "ETH/USDT"


@pytest.fixture()
def config() -> MagicMock:
    return MagicMock(spec=IConfigProvider)


@pytest.fixture()
def manager(config: MagicMock) -> PositionManager:
    return PositionManager(config)


def _make_composite_regime(synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_STRONG_BULL) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=85,
        duration_candles=20,
        transition_probability=0.1,
        recommended_strategies=["momentum"],
        risk_multiplier=1.0,
        max_position_size=0.05,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _make_market_state(indicators: dict | None = None) -> MarketState:
    """Build a minimal MarketState with optional custom indicators."""
    regime = _make_composite_regime()
    if indicators is None:
        indicators = {}
    return MarketState(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        indicators=indicators,
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=True,
        sentinel_data_age_seconds=100,
        btc_price=50_000.0,
        btc_change_1h=0.5,
        btc_change_24h=2.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="markup",
        altcoin_season_index=60,
        fear_greed=70,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _market_state_with_rsi(rsi: float) -> MarketState:
    """Build a MarketState with RSI_14 set on the 5m timeframe for PAIR."""
    return _make_market_state(
        indicators={PAIR: {"5m": {"RSI_14": rsi}}}
    )


def _market_state_no_rsi() -> MarketState:
    """Build a MarketState with no 5m RSI data for PAIR."""
    return _make_market_state(indicators={})


# ===========================================================================
# evaluate_dca — Strong Bull / Breakout Bull / Euphoria (4 levels)
# ===========================================================================

class TestDcaStrongBull:

    def test_dca_strong_bull_level_0(self, manager: PositionManager) -> None:
        """First DCA triggered at -4% in STRONG_BULL regime."""
        ms = _market_state_with_rsi(25.0)  # RSI < 40 → allow
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-4.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"
        assert result["amount_pct"] == 0.50

    def test_dca_strong_bull_level_1(self, manager: PositionManager) -> None:
        """Second DCA triggered at -8% in STRONG_BULL regime."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-8.0, dca_count=1,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"
        assert result["amount_pct"] == 0.30

    def test_dca_strong_bull_level_2(self, manager: PositionManager) -> None:
        """Third DCA triggered at -12% in STRONG_BULL regime."""
        ms = _market_state_with_rsi(15.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-12.5, dca_count=2,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"
        assert result["amount_pct"] == 0.15

    def test_dca_strong_bull_level_3(self, manager: PositionManager) -> None:
        """Fourth (last) DCA triggered at -16% in STRONG_BULL regime."""
        ms = _market_state_with_rsi(10.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-16.0, dca_count=3,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"
        assert result["amount_pct"] == 0.05

    def test_dca_breakout_bull_4_levels(self, manager: PositionManager) -> None:
        """BREAKOUT_BULL also has 4 DCA levels."""
        ms = _market_state_with_rsi(25.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-4.5, dca_count=0,
            regime=SynthesizedRegime.REGIME_BREAKOUT_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"

    def test_dca_euphoria_4_levels(self, manager: PositionManager) -> None:
        """EUPHORIA also has 4 DCA levels."""
        ms = _market_state_with_rsi(25.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_EUPHORIA,
        )
        assert result is not None
        assert result["action"] == "DCA"


# ===========================================================================
# evaluate_dca — Moderate Bull (3 levels)
# ===========================================================================

class TestDcaModerateBull:

    def test_dca_moderate_bull_levels(self, manager: PositionManager) -> None:
        """MODERATE_BULL has 3 levels with thresholds [-3, -6, -10]."""
        ms = _market_state_with_rsi(20.0)

        # Level 0 at -3%
        r0 = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-3.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
        )
        assert r0 is not None and r0["amount_pct"] == 0.50

        # Level 1 at -6%
        r1 = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-6.0, dca_count=1,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
        )
        assert r1 is not None and r1["amount_pct"] == 0.30

        # Level 2 at -10%
        r2 = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-10.5, dca_count=2,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
        )
        assert r2 is not None and r2["amount_pct"] == 0.15

    def test_dca_moderate_bull_max_levels_reached(self, manager: PositionManager) -> None:
        """After 3 DCAs, MODERATE_BULL should return None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-15.0, dca_count=3,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
        )
        assert result is None


# ===========================================================================
# evaluate_dca — Forbidden regimes
# ===========================================================================

class TestDcaForbiddenRegimes:

    def test_dca_forbidden_panic(self, manager: PositionManager) -> None:
        """PANIC regime → always return None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_PANIC,
        )
        assert result is None

    def test_dca_forbidden_strong_bear(self, manager: PositionManager) -> None:
        """STRONG_BEAR regime → always return None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BEAR,
        )
        assert result is None

    def test_dca_forbidden_distribution(self, manager: PositionManager) -> None:
        """DISTRIBUTION regime → always return None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_DISTRIBUTION,
        )
        assert result is None


# ===========================================================================
# evaluate_dca — Max levels reached
# ===========================================================================

class TestDcaMaxLevels:

    def test_dca_max_levels_reached(self, manager: PositionManager) -> None:
        """STRONG_BULL has 4 levels; dca_count=4 → None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-20.0, dca_count=4,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is None

    def test_dca_default_regime_max_levels_reached(self, manager: PositionManager) -> None:
        """Default (WEAK_BULL) has 2 levels; dca_count=2 → None."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-10.0, dca_count=2,
            regime=SynthesizedRegime.REGIME_WEAK_BULL,
        )
        assert result is None


# ===========================================================================
# evaluate_dca — RSI filter
# ===========================================================================

class TestDcaRsiFilter:

    def test_dca_rsi_too_high(self, manager: PositionManager) -> None:
        """RSI >= 40 on 5m → not oversold enough → return None."""
        ms = _market_state_with_rsi(40.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is None

    def test_dca_rsi_above_40_returns_none(self, manager: PositionManager) -> None:
        """RSI = 55 → block DCA."""
        ms = _market_state_with_rsi(55.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is None

    def test_dca_rsi_below_40_allows(self, manager: PositionManager) -> None:
        """RSI = 39 → sufficiently oversold → allow DCA."""
        ms = _market_state_with_rsi(39.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"

    def test_dca_rsi_missing_allows(self, manager: PositionManager) -> None:
        """No RSI data → do not block DCA (allow on missing data)."""
        ms = _market_state_no_rsi()
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is not None
        assert result["action"] == "DCA"

    def test_dca_pnl_not_below_threshold_returns_none(self, manager: PositionManager) -> None:
        """PnL above threshold → return None even with valid RSI."""
        ms = _market_state_with_rsi(20.0)
        result = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-2.0, dca_count=0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
        )
        assert result is None


# ===========================================================================
# evaluate_dca — Default regimes (WEAK_BULL, RANGING, etc.)
# ===========================================================================

class TestDcaDefaultRegimes:

    @pytest.mark.parametrize("regime", [
        SynthesizedRegime.REGIME_WEAK_BULL,
        SynthesizedRegime.REGIME_RANGING_TIGHT,
        SynthesizedRegime.REGIME_RANGING_WIDE,
        SynthesizedRegime.REGIME_CHOPPY,
    ])
    def test_dca_default_regime_2_levels(self, manager: PositionManager, regime: SynthesizedRegime) -> None:
        """Non-specific regimes use 2 levels at [-3, -5]."""
        ms = _market_state_with_rsi(25.0)

        r0 = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-3.0, dca_count=0,
            regime=regime,
        )
        assert r0 is not None and r0["amount_pct"] == 0.50

        r1 = manager.evaluate_dca(
            PAIR, ms, current_pnl_pct=-5.0, dca_count=1,
            regime=regime,
        )
        assert r1 is not None and r1["amount_pct"] == 0.30


# ===========================================================================
# evaluate_derisk
# ===========================================================================

class TestDerisk:

    def test_derisk_level_4(self, manager: PositionManager) -> None:
        """-16% → Level 4, sell 80%."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-16.0, rsi=50.0)
        assert result is not None
        assert result["action"] == "DERISK"
        assert result["level"] == 4
        assert result["sell_pct"] == 0.80
        assert result["reason"] == "Derisk L4: severe loss"

    def test_derisk_level_4_worse_than_16(self, manager: PositionManager) -> None:
        """-20% should also trigger Level 4."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-20.0, rsi=50.0)
        assert result is not None
        assert result["level"] == 4

    def test_derisk_level_3(self, manager: PositionManager) -> None:
        """-12% → Level 3, sell 40%."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-12.0, rsi=50.0)
        assert result is not None
        assert result["action"] == "DERISK"
        assert result["level"] == 3
        assert result["sell_pct"] == 0.40
        assert result["reason"] == "Derisk L3: heavy loss"

    def test_derisk_level_3_between_12_and_16(self, manager: PositionManager) -> None:
        """-14% should trigger Level 3."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-14.0, rsi=50.0)
        assert result is not None
        assert result["level"] == 3

    def test_derisk_level_2(self, manager: PositionManager) -> None:
        """-8% → Level 2, sell 25%."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-8.0, rsi=50.0)
        assert result is not None
        assert result["action"] == "DERISK"
        assert result["level"] == 2
        assert result["sell_pct"] == 0.25
        assert result["reason"] == "Derisk L2: significant loss"

    def test_derisk_level_2_between_8_and_12(self, manager: PositionManager) -> None:
        """-10% should trigger Level 2."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-10.0, rsi=50.0)
        assert result is not None
        assert result["level"] == 2

    def test_derisk_level_1(self, manager: PositionManager) -> None:
        """-5% and RSI >= 30 → Level 1, sell 15%."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-5.0, rsi=35.0)
        assert result is not None
        assert result["action"] == "DERISK"
        assert result["level"] == 1
        assert result["sell_pct"] == 0.15

    def test_derisk_level_1_rsi_skip(self, manager: PositionManager) -> None:
        """-5% but RSI < 30 → too oversold, skip (None)."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-5.0, rsi=25.0)
        assert result is None

    def test_derisk_level_1_rsi_exactly_30_triggers(self, manager: PositionManager) -> None:
        """RSI == 30 is not < 30, so level 1 should trigger."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-5.0, rsi=30.0)
        assert result is not None
        assert result["level"] == 1

    def test_derisk_no_trigger_above_minus5(self, manager: PositionManager) -> None:
        """PnL = -4.9% → no derisk."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-4.9, rsi=50.0)
        assert result is None

    def test_derisk_no_trigger_positive_pnl(self, manager: PositionManager) -> None:
        """Positive PnL → no derisk."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=5.0, rsi=70.0)
        assert result is None

    def test_derisk_level_4_takes_priority_over_lower_levels(self, manager: PositionManager) -> None:
        """-18% triggers L4 not L3."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-18.0, rsi=50.0)
        assert result is not None
        assert result["level"] == 4

    def test_derisk_level_1_rsi_none_triggers(self, manager: PositionManager) -> None:
        """RSI = None at level 1: rsi is None so condition rsi < 30 not met → triggers."""
        result = manager.evaluate_derisk(PAIR, current_pnl_pct=-5.0, rsi=None)
        assert result is not None
        assert result["level"] == 1


# ===========================================================================
# evaluate_buyback
# ===========================================================================

class TestBuyback:

    def test_buyback_conditions_met(self, manager: PositionManager) -> None:
        """All conditions satisfied → return BUYBACK dict."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=70.0,
        )
        assert result is not None
        assert result["action"] == "BUYBACK"
        assert result["size_pct"] == 0.6
        assert "5.0%" in result["reason"]

    def test_buyback_not_profitable(self, manager: PositionManager) -> None:
        """Previous trade not profitable → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=False,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_price_drop_too_small(self, manager: PositionManager) -> None:
        """Price drop <= 3% → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=3.0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_price_drop_exactly_3_not_enough(self, manager: PositionManager) -> None:
        """Price drop exactly 3% → None (must be strictly greater than 3)."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=3.0,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=90.0,
        )
        assert result is None

    def test_buyback_bearish_regime_panic(self, manager: PositionManager) -> None:
        """PANIC regime → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_PANIC,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_bearish_regime_strong_bear(self, manager: PositionManager) -> None:
        """STRONG_BEAR regime → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_STRONG_BEAR,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_bearish_regime_moderate_bear(self, manager: PositionManager) -> None:
        """MODERATE_BEAR regime → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_MODERATE_BEAR,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_bearish_regime_distribution(self, manager: PositionManager) -> None:
        """DISTRIBUTION regime → None."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_DISTRIBUTION,
            confidence=70.0,
        )
        assert result is None

    def test_buyback_high_confidence_sizing(self, manager: PositionManager) -> None:
        """confidence > 80 → size_pct = 0.8."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=4.0,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
            confidence=81.0,
        )
        assert result is not None
        assert result["size_pct"] == 0.8

    def test_buyback_low_confidence_sizing(self, manager: PositionManager) -> None:
        """confidence <= 80 → size_pct = 0.6."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=4.0,
            regime=SynthesizedRegime.REGIME_MODERATE_BULL,
            confidence=80.0,
        )
        assert result is not None
        assert result["size_pct"] == 0.6

    def test_buyback_reason_contains_price_drop(self, manager: PositionManager) -> None:
        """Reason string should include the price drop formatted to 1 decimal."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=7.3,
            regime=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=50.0,
        )
        assert result is not None
        assert "7.3%" in result["reason"]

    def test_buyback_non_bearish_regime_allowed(self, manager: PositionManager) -> None:
        """Non-bearish regimes (e.g., RANGING) should allow buyback."""
        result = manager.evaluate_buyback(
            PAIR,
            prev_profitable=True,
            price_drop_pct=5.0,
            regime=SynthesizedRegime.REGIME_RANGING_TIGHT,
            confidence=60.0,
        )
        assert result is not None
        assert result["action"] == "BUYBACK"
