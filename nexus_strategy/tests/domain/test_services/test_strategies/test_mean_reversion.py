"""Tests for MeanReversionStrategy."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    CompositeRegime,
    MacroRegime,
    MicroRegime,
    MidRegime,
    SynthesizedRegime,
)
from nexus_strategy.domain.models.signal import ExitSignal, Signal
from nexus_strategy.domain.services.strategies.mean_reversion import MeanReversionStrategy


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_market_state(
    pair: str = "BTC/USDT",
    indicators_5m: dict | None = None,
    indicators_15m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_RANGING_TIGHT,
) -> MarketState:
    ind_5m = indicators_5m or {}
    ind_15m = indicators_15m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_RANGING,
        mid=MidRegime.RANGING_TIGHT,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=70,
        duration_candles=5,
        transition_probability=0.0,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={pair: {"5m": ind_5m, "15m": ind_15m, "1h": {}}},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=False,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=1.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=60,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def strategy() -> MeanReversionStrategy:
    return MeanReversionStrategy()


# ---------------------------------------------------------------------------
# 1. test_name_and_optimal_regimes
# ---------------------------------------------------------------------------


class TestMeanReversionMetadata:
    def test_name_and_optimal_regimes(self, strategy: MeanReversionStrategy) -> None:
        assert strategy.name == "MeanReversion"
        assert SynthesizedRegime.REGIME_RANGING_TIGHT in strategy.optimal_regimes
        assert SynthesizedRegime.REGIME_RANGING_WIDE in strategy.optimal_regimes
        assert SynthesizedRegime.REGIME_WEAK_BEAR in strategy.optimal_regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in strategy.optimal_regimes
        assert len(strategy.optimal_regimes) == 4


# ---------------------------------------------------------------------------
# 2. test_oversold_conditions_generate_buy
# ---------------------------------------------------------------------------


class TestOversoldConditionsGenerateBuy:
    def test_oversold_conditions_generate_buy(self, strategy: MeanReversionStrategy) -> None:
        """RSI<30 (+25), close<=BB_lower (+25), MFI<25 (+15), StochRSI<20 (+15) → score=80 → BUY."""
        ind_5m = {
            "RSI_14": 25.0,         # +25
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 99.0,          # close <= BB_lower → +25
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 20.0,         # +15
            "StochRSI_K": 15.0,     # +15
            "Volume_SMA_20": 1000.0,
            "volume": 0.0,          # volume not > 1.5x SMA → no +10
            "CMF_20": 0.0,
            "ATR_14": 2.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "BUY"
        assert signal.confidence >= 50


# ---------------------------------------------------------------------------
# 3. test_normal_conditions_no_signal
# ---------------------------------------------------------------------------


class TestNormalConditionsNoSignal:
    def test_normal_conditions_no_signal(self, strategy: MeanReversionStrategy) -> None:
        """RSI=50, close=BB_mid → no points → NO_SIGNAL."""
        ind_5m = {
            "RSI_14": 50.0,
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 105.0,
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 50.0,
            "StochRSI_K": 50.0,
            "Volume_SMA_20": 1000.0,
            "volume": 500.0,
            "CMF_20": 0.0,
            "ATR_14": 2.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "NO_SIGNAL"
        assert signal.confidence == 0


# ---------------------------------------------------------------------------
# 4. test_moderate_oversold_buy
# ---------------------------------------------------------------------------


class TestModerateOversoldBuy:
    def test_moderate_oversold_buy(self, strategy: MeanReversionStrategy) -> None:
        """RSI<35 (+15), close within 0.5% of BB_lower (+15), MFI<35 (+10), StochRSI<30 (+10) → score=50 → BUY."""
        ind_5m = {
            "RSI_14": 33.0,         # +15
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 100.4,         # within 0.5% above BB_lower → +15
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 30.0,         # +10
            "StochRSI_K": 25.0,     # +10
            "Volume_SMA_20": 1000.0,
            "volume": 0.0,
            "CMF_20": 0.0,
            "ATR_14": 2.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "BUY"


# ---------------------------------------------------------------------------
# 5. test_confidence_capped_at_95
# ---------------------------------------------------------------------------


class TestConfidenceCappedAt95:
    def test_confidence_capped_at_95(self, strategy: MeanReversionStrategy) -> None:
        """Even with maximum score, confidence must not exceed 95."""
        ind_5m = {
            "RSI_14": 25.0,         # +25
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 99.0,          # +25
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 20.0,         # +15
            "StochRSI_K": 15.0,     # +15
            "Volume_SMA_20": 1000.0,
            "volume": 2000.0,       # volume > 1.5x SMA → +10
            "CMF_20": 0.15,         # +10
            "ATR_14": 2.0,
        }
        ind_15m = {"RSI_14": 30.0}  # +10
        ms = _make_market_state(indicators_5m=ind_5m, indicators_15m=ind_15m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "BUY"
        assert signal.confidence <= 95


# ---------------------------------------------------------------------------
# 6. test_stop_loss_below_bb_lower
# ---------------------------------------------------------------------------


class TestStopLossBelowBBLower:
    def test_stop_loss_below_bb_lower(self, strategy: MeanReversionStrategy) -> None:
        """Stop loss = min(BB_lower, close * 0.97)."""
        # close*0.97 = 98.0 * 0.97 = 95.06, BB_lower = 100.0 → stop = 95.06
        ind_5m = {
            "RSI_14": 25.0,
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 98.0,
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 20.0,
            "StochRSI_K": 15.0,
            "Volume_SMA_20": 1000.0,
            "volume": 0.0,
            "CMF_20": 0.0,
            "ATR_14": 2.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "BUY"
        expected_sl = min(100.0, 98.0 * 0.97)
        assert abs(signal.stop_loss - expected_sl) < 1e-6
        assert signal.stop_loss < 100.0  # Stop must be below BB_lower


# ---------------------------------------------------------------------------
# 7. test_take_profit_levels_set
# ---------------------------------------------------------------------------


class TestTakeProfitLevelsSet:
    def test_take_profit_levels_set(self, strategy: MeanReversionStrategy) -> None:
        """Take profit levels: BB_mid (25%), EMA_50 (25%), BB_upper (25%), EMA_50*1.02 (25%)."""
        ind_5m = {
            "RSI_14": 25.0,
            "BB_lower_20": 100.0,
            "BB_upper_20": 110.0,
            "BB_mid_20": 105.0,
            "close": 99.0,
            "EMA_50": 106.0,
            "EMA_21": 104.0,
            "MFI_14": 20.0,
            "StochRSI_K": 15.0,
            "Volume_SMA_20": 1000.0,
            "volume": 0.0,
            "CMF_20": 0.0,
            "ATR_14": 2.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "BUY"
        assert len(signal.take_profit_levels) == 4

        total_pct = sum(tp["pct"] for tp in signal.take_profit_levels)
        assert abs(total_pct - 1.0) < 1e-6

        prices = [tp["price"] for tp in signal.take_profit_levels]
        assert prices[0] == 105.0            # BB_mid
        assert prices[1] == 106.0            # EMA_50
        assert prices[2] == 110.0            # BB_upper
        assert abs(prices[3] - 106.0 * 1.02) < 1e-6  # EMA_50 * 1.02


# ---------------------------------------------------------------------------
# 8. test_exit_rsi_overbought
# ---------------------------------------------------------------------------


class TestExitRsiOverbought:
    def test_exit_rsi_overbought(self, strategy: MeanReversionStrategy) -> None:
        """RSI > 75 → should_exit=True, urgency=70, partial_pct=0.5, reason contains 'RSI overbought'."""
        ind_5m = {
            "RSI_14": 80.0,
            "close": 108.0,
            "BB_upper_20": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        exit_signal = strategy.generate_exit_signal("BTC/USDT", ms, 100.0, 8.0)

        assert exit_signal.should_exit is True
        assert exit_signal.urgency == 70
        assert exit_signal.partial_pct == 0.5
        assert "RSI overbought" in exit_signal.reason


# ---------------------------------------------------------------------------
# 9. test_exit_above_bb_upper
# ---------------------------------------------------------------------------


class TestExitAboveBBUpper:
    def test_exit_above_bb_upper(self, strategy: MeanReversionStrategy) -> None:
        """Close > BB_upper → full exit, urgency=75, partial_pct=1.0."""
        ind_5m = {
            "RSI_14": 65.0,  # Not >75, RSI check does not fire
            "close": 112.0,
            "BB_upper_20": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        exit_signal = strategy.generate_exit_signal("BTC/USDT", ms, 100.0, 12.0)

        assert exit_signal.should_exit is True
        assert exit_signal.urgency == 75
        assert exit_signal.partial_pct == 1.0
        assert "BB upper" in exit_signal.reason


# ---------------------------------------------------------------------------
# 10. test_exit_profit_target
# ---------------------------------------------------------------------------


class TestExitProfitTarget:
    def test_exit_profit_target(self, strategy: MeanReversionStrategy) -> None:
        """PnL > 3% and RSI > 60 → partial exit, urgency=50."""
        ind_5m = {
            "RSI_14": 65.0,
            "close": 103.5,
            "BB_upper_20": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        exit_signal = strategy.generate_exit_signal("BTC/USDT", ms, 100.0, 3.5)

        assert exit_signal.should_exit is True
        assert exit_signal.urgency == 50
        assert exit_signal.partial_pct == 0.5
        assert "Profit target" in exit_signal.reason


# ---------------------------------------------------------------------------
# 11. test_no_exit_normal_conditions
# ---------------------------------------------------------------------------


class TestNoExitNormalConditions:
    def test_no_exit_normal_conditions(self, strategy: MeanReversionStrategy) -> None:
        """RSI and price within normal range → no exit."""
        ind_5m = {
            "RSI_14": 55.0,
            "close": 105.0,
            "BB_upper_20": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        exit_signal = strategy.generate_exit_signal("BTC/USDT", ms, 100.0, 2.0)

        assert exit_signal.should_exit is False
        assert exit_signal.urgency == 0


# ---------------------------------------------------------------------------
# 12. test_missing_indicators_no_crash
# ---------------------------------------------------------------------------


class TestMissingIndicatorsNoCrash:
    def test_missing_indicators_no_crash(self, strategy: MeanReversionStrategy) -> None:
        """Empty 5m indicators dict should return NO_SIGNAL without raising."""
        ms = _make_market_state(indicators_5m={})
        signal = strategy.generate_signal("BTC/USDT", ms)

        assert signal.action == "NO_SIGNAL"
        assert isinstance(signal, Signal)


# ---------------------------------------------------------------------------
# 13. test_regime_active_ranging_tight
# ---------------------------------------------------------------------------


class TestRegimeActiveRangingTight:
    def test_regime_active_ranging_tight(self, strategy: MeanReversionStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_TIGHT) is True


# ---------------------------------------------------------------------------
# 14. test_regime_inactive_strong_bull
# ---------------------------------------------------------------------------


class TestRegimeInactiveStrongBull:
    def test_regime_inactive_strong_bull(self, strategy: MeanReversionStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is False
