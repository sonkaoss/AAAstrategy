"""Tests for VolatilitySqueezeStrategy."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    CompositeRegime,
    MacroRegime,
    MicroRegime,
    MidRegime,
    SynthesizedRegime,
)
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.volatility_squeeze import VolatilitySqueezeStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_market_state(
    pair: str = "ETH/USDT",
    indicators_5m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_SQUEEZE,
) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_SQUEEZE,
        mid=MidRegime.RANGING_TIGHT,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=65,
        duration_candles=10,
        transition_probability=0.1,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={pair: {"5m": ind_5m, "15m": {}, "1h": {}}},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=False,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.3,
        btc_change_24h=1.5,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=55,
        fear_greed=50,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _squeeze_bullish_indicators_keltner(close: float = 100.0) -> dict:
    """BB strictly inside Keltner + all bullish direction indicators."""
    atr = 0.5
    return {
        # BB strictly inside Keltner
        "BB_upper_20": close + 1.0,
        "BB_lower_20": close - 1.0,
        "BB_width_20": 0.05,          # not tight on its own; squeeze via keltner
        "Keltner_upper": close + 2.0,
        "Keltner_lower": close - 2.0,  # keltner_lower > 0 => valid
        "ATR_14": atr,
        # All bullish direction conditions
        "RSI_14": 55.0,               # > 50 => +15
        "MACD_hist": 0.001,           # > 0  => +15
        "EMA_9": close + 0.1,         # > EMA_21 => +10
        "EMA_21": close - 0.1,
        "ROC_9": 0.5,                 # > 0 => +10
        "close": close + 0.1,         # in upper half of BB range => +10
        "ADX_14": 25.0,               # not < 20
    }


def _squeeze_bullish_indicators_width(close: float = 100.0) -> dict:
    """BB_width tight AND adx < 20 (combined condition) + all bullish direction indicators."""
    atr = 0.02
    return {
        # Keltner inverted/invalid so bb_inside_keltner = False
        "BB_upper_20": close + 0.01,
        "BB_lower_20": close - 0.01,
        "BB_width_20": 0.02,          # < 0.03 => part of bb_width_squeeze
        "Keltner_upper": 0.0,         # keltner_upper <= 0 => invalid
        "Keltner_lower": 0.0,
        "ATR_14": atr,
        # All bullish direction conditions
        "RSI_14": 55.0,               # > 50 => +15
        "MACD_hist": 0.001,           # > 0  => +15
        "EMA_9": close + 0.001,       # > EMA_21 => +10
        "EMA_21": close - 0.001,
        "ROC_9": 0.5,                 # > 0 => +10
        "close": close + 0.005,       # upper half of BB range => +10
        "ADX_14": 15.0,               # < 20 => bb_width_squeeze triggered
    }


# ---------------------------------------------------------------------------
# Strategy metadata tests
# ---------------------------------------------------------------------------

class TestVolatilitySqueezeMetadata:
    def test_name(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.name == "VolatilitySqueeze"

    def test_optimal_regimes(self) -> None:
        strat = VolatilitySqueezeStrategy()
        regimes = strat.optimal_regimes
        assert SynthesizedRegime.REGIME_SQUEEZE in regimes
        assert SynthesizedRegime.REGIME_RANGING_TIGHT in regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in regimes

    def test_active_for_squeeze_regime(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_SQUEEZE) is True

    def test_active_for_ranging_tight(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_TIGHT) is True

    def test_active_for_accumulation(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_ACCUMULATION) is True

    def test_inactive_for_strong_bull(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is False

    def test_inactive_for_panic(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False


# ---------------------------------------------------------------------------
# Entry signal — BUY tests
# ---------------------------------------------------------------------------

class TestGenerateSignalBuy:
    def test_keltner_squeeze_and_bullish_direction_gives_buy(self) -> None:
        """BB strictly inside Keltner + bullish direction => BUY."""
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert isinstance(sig, Signal)
        assert sig.action == "BUY"
        assert sig.is_buy is True
        assert sig.pair == "ETH/USDT"
        assert sig.strategy_name == "VolatilitySqueeze"

    def test_width_adx_squeeze_and_bullish_direction_gives_buy(self) -> None:
        """BB_width < 0.03 AND ADX < 20 + bullish direction => BUY."""
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_width(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert isinstance(sig, Signal)
        assert sig.action == "BUY"
        assert sig.is_buy is True

    def test_buy_signal_confidence_range(self) -> None:
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert sig.action == "BUY"
        assert 0 < sig.confidence <= 90

    def test_buy_confidence_formula_max(self) -> None:
        """direction_score=60 => confidence=min(40+60,90)=90."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = _squeeze_bullish_indicators_keltner(close)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert sig.action == "BUY"
        assert sig.confidence == 90

    def test_buy_signal_has_three_tp_levels(self) -> None:
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert sig.action == "BUY"
        assert len(sig.take_profit_levels) == 3

    def test_take_profit_percentages_sum_to_one(self) -> None:
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        total_pct = sum(tp["pct"] for tp in sig.take_profit_levels)
        assert abs(total_pct - 1.0) < 1e-9

    def test_take_profit_prices_ascending_and_above_entry(self) -> None:
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = _squeeze_bullish_indicators_keltner(close)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        prices = [tp["price"] for tp in sig.take_profit_levels]
        assert prices == sorted(prices)
        entry = sig.entry_price
        assert all(p > entry for p in prices)

    def test_stop_loss_below_entry(self) -> None:
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert sig.stop_loss < sig.entry_price

    def test_stop_loss_is_max_of_bb_lower_and_atr_based(self) -> None:
        """stop_loss = max(BB_lower, close - ATR*2).

        We set all values explicitly to ensure the actual 'close' indicator
        used for stop_loss calculation is known.
        """
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        atr = 0.02
        # BB strictly inside Keltner: bb_lower > keltner_lower AND bb_upper < keltner_upper
        bb_lower = close - 0.5   # 99.5; close-atr*2 = 99.96 => max = close-atr*2
        bb_upper = close + 0.5
        keltner_lower = close - 1.0
        keltner_upper = close + 1.0
        ind = {
            "BB_upper_20": bb_upper,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.05,
            "Keltner_upper": keltner_upper,
            "Keltner_lower": keltner_lower,
            "ATR_14": atr,
            "RSI_14": 55.0,
            "MACD_hist": 0.001,
            "EMA_9": close + 0.1,
            "EMA_21": close - 0.1,
            "ROC_9": 0.5,
            "close": close,        # upper half: close > (bb_lower + range/2) = close => not strictly => no bonus
            "ADX_14": 25.0,
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert sig.action == "BUY"
        expected_sl = max(bb_lower, close - atr * 2.0)
        assert abs(sig.stop_loss - expected_sl) < 1e-9

    def test_signal_has_correct_indicators_used(self) -> None:
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)

        assert "RSI_14" in sig.indicators_used
        assert "ATR_14" in sig.indicators_used
        assert "ADX_14" in sig.indicators_used
        assert "MACD_hist" in sig.indicators_used


# ---------------------------------------------------------------------------
# Entry signal — NO_SIGNAL tests
# ---------------------------------------------------------------------------

class TestGenerateSignalNoSignal:
    def test_no_squeeze_conditions_returns_no_signal(self) -> None:
        """BB wider than Keltner, bb_width >= 0.03, ADX >= 20 => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = {
            # BB wider than Keltner => NOT inside
            "BB_upper_20": close + 5.0,
            "BB_lower_20": close - 5.0,
            "BB_width_20": 0.10,        # >= 0.03 => not tight
            "Keltner_upper": close + 3.0,
            "Keltner_lower": close - 3.0,
            "ATR_14": 1.0,
            "RSI_14": 60.0,
            "MACD_hist": 0.01,
            "EMA_9": close + 0.5,
            "EMA_21": close - 0.5,
            "ROC_9": 1.0,
            "close": close,
            "ADX_14": 30.0,             # >= 20 => bb_width_squeeze needs adx<20
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False

    def test_squeeze_detected_but_bearish_direction_no_signal(self) -> None:
        """Keltner squeeze but all bearish direction => direction_score=0 < 35 => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = {
            "BB_upper_20": close + 1.0,
            "BB_lower_20": close - 1.0,
            "BB_width_20": 0.05,
            "Keltner_upper": close + 2.0,
            "Keltner_lower": close - 2.0,
            "ATR_14": 0.5,
            # All bearish / neutral
            "RSI_14": 45.0,            # <= 50 => no points
            "MACD_hist": -0.01,        # < 0 => no points
            "EMA_9": close - 0.01,     # < EMA_21 => no points
            "EMA_21": close + 0.01,
            "ROC_9": -1.0,             # < 0 => no points
            "close": close - 0.5,      # in lower half of BB range => no points
            "ADX_14": 25.0,
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "NO_SIGNAL"

    def test_bb_width_tight_but_adx_high_no_signal(self) -> None:
        """BB_width < 0.03 but ADX >= 20 => bb_width_squeeze False; no keltner squeeze => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        close = 1.0
        ind = {
            "BB_upper_20": close + 0.01,
            "BB_lower_20": close - 0.01,
            "BB_width_20": 0.02,        # tight but...
            "Keltner_upper": 0.0,       # invalid keltner => no keltner squeeze
            "Keltner_lower": 0.0,
            "ATR_14": 0.02,
            "RSI_14": 55.0,
            "MACD_hist": 0.001,
            "EMA_9": close + 0.001,
            "EMA_21": close - 0.001,
            "ROC_9": 0.5,
            "close": close + 0.005,
            "ADX_14": 25.0,             # >= 20 => bb_width_squeeze = False
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "NO_SIGNAL"

    def test_adx_low_but_bb_width_not_tight_no_signal(self) -> None:
        """ADX < 20 but BB_width >= 0.03 => bb_width_squeeze False; no keltner squeeze => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        close = 1.0
        ind = {
            "BB_upper_20": close + 0.5,
            "BB_lower_20": close - 0.5,
            "BB_width_20": 0.05,        # >= 0.03 => not tight
            "Keltner_upper": 0.0,       # invalid
            "Keltner_lower": 0.0,
            "ATR_14": 0.05,
            "RSI_14": 55.0,
            "MACD_hist": 0.001,
            "EMA_9": close + 0.01,
            "EMA_21": close - 0.01,
            "ROC_9": 0.5,
            "close": close + 0.1,
            "ADX_14": 10.0,             # < 20 but bb_width not tight
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "NO_SIGNAL"

    def test_direction_score_below_35_no_signal(self) -> None:
        """Keltner squeeze but direction_score=30 (RSI+MACD only) < 35 => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = {
            "BB_upper_20": close + 1.0,
            "BB_lower_20": close - 1.0,
            "BB_width_20": 0.05,
            "Keltner_upper": close + 2.0,
            "Keltner_lower": close - 2.0,
            "ATR_14": 0.5,
            "RSI_14": 60.0,     # +15
            "MACD_hist": 0.001, # +15
            # total = 30 < 35
            "EMA_9": close - 0.01,   # no points
            "EMA_21": close + 0.01,
            "ROC_9": -0.5,           # no points
            "close": close,          # at midpoint => no upper-half bonus
            "ADX_14": 25.0,
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "NO_SIGNAL"

    def test_missing_indicators_defaults_no_signal(self) -> None:
        """With all indicators missing (defaults 0), no valid squeeze => NO_SIGNAL."""
        strat = VolatilitySqueezeStrategy()
        ms = _make_market_state(indicators_5m={})
        sig = strat.generate_signal("ETH/USDT", ms)
        # keltner_lower=0 and keltner_upper=0 => bb_inside_keltner False
        # bb_width=0 < 0.03 but adx=0 < 20 => bb_width_squeeze True
        # direction: RSI=0<=50, MACD=0 not >0, EMA_9=EMA_21=0 (not >), ROC=0 not >0
        # bb_range=0 => no upper-half bonus => direction_score=0 < 35 => NO_SIGNAL
        assert sig.action == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# Exit signal tests
# ---------------------------------------------------------------------------

class TestGenerateExitSignal:
    def test_exit_wrong_direction_close_below_bb_lower(self) -> None:
        """Close < BB lower triggers urgent full exit."""
        strat = VolatilitySqueezeStrategy()
        close = 99.0
        bb_lower = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.02,
            "EMA_21": 101.0,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 105.0, -5.0)

        assert ex.should_exit is True
        assert ex.urgency == 90
        assert ex.partial_pct == 1.0
        assert ex.exit_layer == ExitLayer.TECHNICAL

    def test_exit_bb_expanding_below_ema21(self) -> None:
        """BB expanding (>0.06) + close below EMA_21 triggers partial exit."""
        strat = VolatilitySqueezeStrategy()
        close = 99.0
        bb_lower = 95.0   # close > bb_lower so no wrong-direction exit
        ema_21 = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.07,     # > 0.06 => expanding
            "EMA_21": ema_21,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 105.0, -4.0)

        assert ex.should_exit is True
        assert ex.urgency == 60
        assert ex.partial_pct == 0.5
        assert ex.exit_layer == ExitLayer.TECHNICAL

    def test_no_exit_when_conditions_not_met(self) -> None:
        """Close above BB lower and BB not expanding => no exit."""
        strat = VolatilitySqueezeStrategy()
        close = 102.0
        bb_lower = 99.0
        ema_21 = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.02,     # not expanding
            "EMA_21": ema_21,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 100.0, 2.0)

        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_no_exit_when_bb_expanding_but_close_above_ema21(self) -> None:
        """BB expanding but close >= EMA_21 => no exit (bullish breakout)."""
        strat = VolatilitySqueezeStrategy()
        close = 105.0
        bb_lower = 99.0
        ema_21 = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.07,     # > 0.06, expanding
            "EMA_21": ema_21,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 100.0, 5.0)

        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_wrong_direction_exit_takes_priority_over_partial(self) -> None:
        """Even with expanding BB, close < bb_lower = full exit at urgency 90."""
        strat = VolatilitySqueezeStrategy()
        close = 94.0
        bb_lower = 95.0
        ema_21 = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.07,     # expanding
            "EMA_21": ema_21,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 100.0, -6.0)

        assert ex.should_exit is True
        assert ex.urgency == 90
        assert ex.partial_pct == 1.0

    def test_no_exit_bb_width_just_below_threshold(self) -> None:
        """BB_width at 0.06 (not > 0.06) => no partial exit triggered."""
        strat = VolatilitySqueezeStrategy()
        close = 99.0
        bb_lower = 95.0
        ema_21 = 100.0
        ind = {
            "close": close,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.06,     # exactly 0.06, NOT > 0.06
            "EMA_21": ema_21,
        }
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("ETH/USDT", ms, 100.0, -1.0)

        assert ex.should_exit is False


# ---------------------------------------------------------------------------
# Regime filtering tests
# ---------------------------------------------------------------------------

class TestRegimeFiltering:
    def test_regime_squeeze_is_active(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_SQUEEZE) is True

    def test_regime_ranging_tight_is_active(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_TIGHT) is True

    def test_regime_accumulation_is_active(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_ACCUMULATION) is True

    def test_regime_strong_bull_is_inactive(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is False

    def test_regime_moderate_bear_is_inactive(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_MODERATE_BEAR) is False

    def test_regime_breakout_bull_is_inactive(self) -> None:
        strat = VolatilitySqueezeStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_BREAKOUT_BULL) is False


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_partial_bullish_direction_score_40_gives_buy(self) -> None:
        """direction_score=40 (RSI+MACD+ROC=15+15+10) => confidence=min(80,90)=80."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        ind = {
            "BB_upper_20": close + 1.0,
            "BB_lower_20": close - 1.0,
            "BB_width_20": 0.05,
            "Keltner_upper": close + 2.0,
            "Keltner_lower": close - 2.0,
            "ATR_14": 0.5,
            "RSI_14": 60.0,        # +15
            "MACD_hist": 0.001,    # +15
            "EMA_9": close - 0.01, # no points (< EMA_21)
            "EMA_21": close + 0.01,
            "ROC_9": 1.0,          # +10
            "close": close,        # at midpoint => no upper-half bonus
            "ADX_14": 25.0,
        }
        # direction_score = 40
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "BUY"
        assert sig.confidence == min(40 + 40, 90)

    def test_confidence_capped_at_90(self) -> None:
        """Max direction_score=60 => confidence=min(100,90)=90."""
        strat = VolatilitySqueezeStrategy()
        ind = _squeeze_bullish_indicators_keltner(100.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "BUY"
        assert sig.confidence <= 90

    def test_stop_loss_respects_atr_when_higher(self) -> None:
        """When close - ATR*2 > BB_lower, stop_loss should equal close - ATR*2.

        Uses bb_width_squeeze (bb_width < 0.03 AND adx < 20) to trigger squeeze,
        so BB_lower can be set freely without needing Keltner constraints.
        """
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        atr = 0.5
        bb_lower = 95.0
        # close - atr*2 = 99.0 > bb_lower = 95.0 => max = 99.0
        ind = {
            "BB_upper_20": close + 0.01,
            "BB_lower_20": bb_lower,
            "BB_width_20": 0.02,           # < 0.03
            "Keltner_upper": 0.0,          # invalid keltner => no keltner squeeze
            "Keltner_lower": 0.0,
            "ATR_14": atr,
            "RSI_14": 55.0,     # +15
            "MACD_hist": 0.001, # +15
            "EMA_9": close + 0.1,  # > EMA_21 => +10
            "EMA_21": close - 0.1,
            "ROC_9": 0.5,       # +10 — total = 50 >= 35
            "close": close,
            "ADX_14": 15.0,     # < 20 => bb_width_squeeze triggered
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "BUY"
        expected_sl = max(bb_lower, close - atr * 2.0)
        assert abs(sig.stop_loss - expected_sl) < 1e-9

    def test_bb_width_and_adx_squeeze_direction_score_35(self) -> None:
        """Using bb_width_squeeze path with direction_score exactly >= 35."""
        strat = VolatilitySqueezeStrategy()
        close = 1.0
        ind = {
            "BB_upper_20": close + 0.01,
            "BB_lower_20": close - 0.01,
            "BB_width_20": 0.02,           # < 0.03
            "Keltner_upper": 0.0,          # invalid => no keltner squeeze
            "Keltner_lower": 0.0,
            "ATR_14": 0.02,
            "RSI_14": 55.0,     # +15
            "MACD_hist": 0.001, # +15
            "EMA_9": close + 0.001,  # > EMA_21 => +10
            "EMA_21": close - 0.001,
            "ROC_9": -0.5,      # no points
            "close": close,     # at midpoint => no upper-half bonus
            "ADX_14": 15.0,     # < 20 => bb_width_squeeze triggered
        }
        # direction_score = 15+15+10 = 40 >= 35 => BUY
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "BUY"
        assert sig.confidence == min(40 + 40, 90)

    def test_tp_levels_use_atr_multiples(self) -> None:
        """TP levels should be close + ATR*2, close + ATR*3, close + ATR*5."""
        strat = VolatilitySqueezeStrategy()
        close = 100.0
        atr = 1.0
        ind = _squeeze_bullish_indicators_keltner(close)
        ind["ATR_14"] = atr
        ind["close"] = close
        # Adjust bb/keltner to match close
        ind["BB_upper_20"] = close + 0.5
        ind["BB_lower_20"] = close - 0.5
        ind["Keltner_upper"] = close + 1.5
        ind["Keltner_lower"] = close - 1.5
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.action == "BUY"
        prices = [tp["price"] for tp in sig.take_profit_levels]
        assert abs(prices[0] - (close + atr * 2)) < 1e-9
        assert abs(prices[1] - (close + atr * 3)) < 1e-9
        assert abs(prices[2] - (close + atr * 5)) < 1e-9
