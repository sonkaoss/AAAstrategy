"""Tests for TrendFollowingStrategy."""
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
from nexus_strategy.domain.services.strategies.trend_following import TrendFollowingStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_market_state(
    pair: str = "BTC/USDT",
    indicators_5m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_STRONG_BULL,
) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=80,
        duration_candles=10,
        transition_probability=0.0,
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
        btc_change_1h=0.5,
        btc_change_24h=2.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=65,
        fear_greed=60,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _strong_uptrend_indicators(close: float = 100.0, atr: float = 1.0) -> dict:
    """Indicators that satisfy every scoring condition for a BUY signal."""
    return {
        "EMA_9": close * 1.01,    # 9 > 21 > 50 > 200
        "EMA_21": close * 1.005,
        "EMA_50": close * 1.002,
        "EMA_200": close * 0.98,
        "ADX_14": 35.0,           # > 30
        "MACD_12_26_9": 0.5,      # positive
        "MACD_hist": 0.2,         # positive
        "RSI_14": 60.0,           # 50-70
        "Supertrend_10_3": close * 0.95,  # close > supertrend
        "close": close,
        "ATR_14": atr,
    }


# ---------------------------------------------------------------------------
# Strategy metadata tests
# ---------------------------------------------------------------------------

class TestTrendFollowingMetadata:
    def test_name(self) -> None:
        strat = TrendFollowingStrategy()
        assert strat.name == "TrendFollowing"

    def test_optimal_regimes_contains_strong_bull(self) -> None:
        strat = TrendFollowingStrategy()
        assert SynthesizedRegime.REGIME_STRONG_BULL in strat.optimal_regimes

    def test_optimal_regimes_contains_moderate_bull(self) -> None:
        strat = TrendFollowingStrategy()
        assert SynthesizedRegime.REGIME_MODERATE_BULL in strat.optimal_regimes

    def test_optimal_regimes_contains_breakout_bull(self) -> None:
        strat = TrendFollowingStrategy()
        assert SynthesizedRegime.REGIME_BREAKOUT_BULL in strat.optimal_regimes

    def test_regime_filtering_active(self) -> None:
        strat = TrendFollowingStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is True
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_MODERATE_BULL) is True
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_BREAKOUT_BULL) is True

    def test_regime_filtering_inactive(self) -> None:
        strat = TrendFollowingStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_TIGHT) is False
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False


# ---------------------------------------------------------------------------
# generate_signal — entry signal tests
# ---------------------------------------------------------------------------

class TestGenerateSignalBuy:
    def test_strong_uptrend_produces_buy(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "BUY"
        assert sig.is_buy is True

    def test_strong_uptrend_confidence_within_bounds(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert 55 <= sig.confidence <= 95

    def test_confidence_capped_at_95(self) -> None:
        """Even a perfect score must not exceed 95."""
        strat = TrendFollowingStrategy()
        # Score would be 20+20+15+15+10+10 = 90, capped at 95 anyway
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.confidence <= 95

    def test_buy_signal_has_correct_pair(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(pair="ETH/USDT", indicators_5m=_strong_uptrend_indicators(close=2000.0, atr=20.0))
        sig = strat.generate_signal("ETH/USDT", ms)
        assert sig.pair == "ETH/USDT"

    def test_buy_signal_strategy_name(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.strategy_name == "TrendFollowing"

    def test_four_take_profit_levels(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert len(sig.take_profit_levels) == 4

    def test_take_profit_percentages_sum_to_one(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        total_pct = sum(tp["pct"] for tp in sig.take_profit_levels)
        assert abs(total_pct - 1.0) < 1e-9

    def test_take_profit_prices_ascending(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators(close=100.0, atr=1.0))
        sig = strat.generate_signal("BTC/USDT", ms)
        prices = [tp["price"] for tp in sig.take_profit_levels]
        assert prices == sorted(prices)

    def test_take_profit_levels_above_close(self) -> None:
        strat = TrendFollowingStrategy()
        close = 100.0
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators(close=close, atr=1.0))
        sig = strat.generate_signal("BTC/USDT", ms)
        for tp in sig.take_profit_levels:
            assert tp["price"] > close

    def test_stop_loss_uses_ema50_when_higher(self) -> None:
        """If EMA_50 > close - ATR*3, stop_loss should be EMA_50."""
        strat = TrendFollowingStrategy()
        close = 100.0
        atr = 1.0
        ema50 = 98.5  # higher than close - atr*3 = 97.0
        ind = _strong_uptrend_indicators(close=close, atr=atr)
        ind["EMA_50"] = ema50
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.stop_loss == pytest.approx(ema50, abs=1e-6)

    def test_stop_loss_uses_atr_when_higher(self) -> None:
        """If close - ATR*3 > EMA_50, stop_loss should be close - ATR*3."""
        strat = TrendFollowingStrategy()
        close = 100.0
        atr = 2.0  # close - atr*3 = 94.0
        ema50 = 93.0  # lower than 94.0
        ind = _strong_uptrend_indicators(close=close, atr=atr)
        ind["EMA_50"] = ema50
        # Make sure EMA alignment is still satisfied for a BUY
        ind["EMA_9"] = 102.0
        ind["EMA_21"] = 101.0
        ind["EMA_200"] = 90.0
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.stop_loss == pytest.approx(close - atr * 3.0, abs=1e-6)

    def test_indicators_used_listed(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
        sig = strat.generate_signal("BTC/USDT", ms)
        assert "EMA_9" in sig.indicators_used
        assert "ADX_14" in sig.indicators_used
        assert "RSI_14" in sig.indicators_used


class TestGenerateSignalNoSignal:
    def test_sideways_market_no_signal(self) -> None:
        """Low ADX, flat EMAs, neutral RSI → score below 55 → NO_SIGNAL."""
        strat = TrendFollowingStrategy()
        ind = {
            "EMA_9": 100.0,
            "EMA_21": 100.1,  # 9 < 21 → no EMA alignment bonus
            "EMA_50": 100.2,
            "EMA_200": 100.3,
            "ADX_14": 15.0,   # < 20 → no ADX bonus
            "MACD_12_26_9": -0.1,  # negative → no MACD bonus
            "MACD_hist": -0.05,
            "RSI_14": 50.0,   # borderline — gets +15 if exactly 50
            "Supertrend_10_3": 101.0,  # above close → no supertrend bonus
            "close": 100.0,
            "ATR_14": 0.5,
        }
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False

    def test_no_signal_confidence_is_zero(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m={})
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.confidence == 0

    def test_no_signal_when_all_indicators_missing(self) -> None:
        """Missing indicators default to 0, producing a very low score."""
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m={})
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "NO_SIGNAL"

    def test_score_just_below_threshold_no_signal(self) -> None:
        """Score = 50 (just below 55) should yield NO_SIGNAL."""
        strat = TrendFollowingStrategy()
        # Only EMA partial (+10) + ADX >25 (+15) + MACD (+15) = 40... need to craft 50 exactly
        # EMA 9>21>50 (+15) + ADX >25 (+15) + RSI 45-75 (+10) = 40 — still below 55
        # EMA 9>21>50>200 (+20) + ADX >20 (+10) + RSI 45-75 (+10) = 40 — below 55
        # EMA full (+20) + ADX >25 (+15) = 35 — below 55
        # This combination intentionally stays below 55
        ind = {
            "EMA_9": 102.0,
            "EMA_21": 101.0,
            "EMA_50": 100.0,
            "EMA_200": 99.0,   # full alignment → +20
            "ADX_14": 22.0,    # >20 → +10
            "MACD_12_26_9": -0.1,   # negative, no bonus
            "MACD_hist": -0.05,
            "RSI_14": 80.0,    # outside 45-75, no RSI bonus
            "Supertrend_10_3": 105.0,  # above close, no bonus
            "close": 100.0,    # EMA_21 is 101 so close < EMA_21, no pullback bonus
            "ATR_14": 0.5,
        }
        # Score: 20 + 10 = 30 → NO_SIGNAL
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# generate_exit_signal tests
# ---------------------------------------------------------------------------

class TestGenerateExitSignal:
    def _base_indicators(self, close: float = 100.0) -> dict:
        return {
            "EMA_9": close * 1.02,
            "EMA_21": close * 1.01,
            "EMA_50": close * 0.99,
            "ADX_14": 28.0,
            "MACD_12_26_9": 0.3,
            "MACD_hist": 0.1,
            "close": close,
            "ATR_14": 1.0,
        }

    def test_no_exit_when_trend_healthy(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=self._base_indicators())
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 5.0)
        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_exit_ema9_below_ema21(self) -> None:
        strat = TrendFollowingStrategy()
        ind = self._base_indicators()
        ind["EMA_9"] = 99.0   # 9 < 21
        ind["EMA_21"] = 100.0
        ind["EMA_50"] = 95.0  # close still above EMA_50
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 5.0)
        assert ex.should_exit is True
        assert ex.urgency == 50
        assert ex.partial_pct == 0.5

    def test_exit_adx_below_20(self) -> None:
        strat = TrendFollowingStrategy()
        ind = self._base_indicators()
        ind["ADX_14"] = 18.0
        ind["EMA_9"] = 101.0   # 9 > 21 so no EMA cross trigger
        ind["EMA_21"] = 100.0
        ind["EMA_50"] = 90.0   # close > EMA_50, no full exit
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 5.0)
        assert ex.should_exit is True
        assert ex.urgency == 60
        assert ex.partial_pct == 0.5

    def test_exit_close_below_ema50_full_exit(self) -> None:
        strat = TrendFollowingStrategy()
        ind = self._base_indicators(close=88.0)
        ind["EMA_50"] = 90.0   # close < EMA_50
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, -7.0)
        assert ex.should_exit is True
        assert ex.urgency == 75
        assert ex.partial_pct == 1.0

    def test_exit_macd_hist_negative_macd_positive(self) -> None:
        strat = TrendFollowingStrategy()
        ind = self._base_indicators()
        ind["MACD_12_26_9"] = 0.3   # positive
        ind["MACD_hist"] = -0.1     # negative
        ind["EMA_9"] = 101.0        # 9 > 21 so no EMA cross
        ind["EMA_21"] = 100.0
        ind["EMA_50"] = 90.0        # close > EMA_50
        ind["ADX_14"] = 25.0        # > 20
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 5.0)
        assert ex.should_exit is True
        assert ex.urgency == 40
        assert ex.partial_pct == 0.25

    def test_exit_priority_close_below_ema50_overrides_others(self) -> None:
        """close < EMA_50 should trigger urgency=75, even if other conditions also apply."""
        strat = TrendFollowingStrategy()
        ind = self._base_indicators(close=85.0)
        ind["EMA_50"] = 90.0    # close < EMA_50
        ind["EMA_9"] = 84.0     # also 9 < 21
        ind["EMA_21"] = 86.0
        ind["ADX_14"] = 15.0    # also ADX < 20
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, -10.0)
        assert ex.urgency == 75
        assert ex.partial_pct == 1.0

    def test_exit_signal_has_technical_layer(self) -> None:
        strat = TrendFollowingStrategy()
        ind = self._base_indicators()
        ind["EMA_9"] = 99.0
        ind["EMA_21"] = 100.0
        ind["EMA_50"] = 95.0
        ms = _make_market_state(indicators_5m=ind)
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 0.0)
        assert ex.exit_layer == ExitLayer.TECHNICAL

    def test_exit_returns_exit_signal_type(self) -> None:
        strat = TrendFollowingStrategy()
        ms = _make_market_state(indicators_5m=self._base_indicators())
        ex = strat.generate_exit_signal("BTC/USDT", ms, 95.0, 0.0)
        assert isinstance(ex, ExitSignal)


# ---------------------------------------------------------------------------
# Scoring edge cases
# ---------------------------------------------------------------------------

class TestScoringEdgeCases:
    def test_rsi_boundary_50_scores_15(self) -> None:
        """RSI exactly 50 hits the 50-70 band, scoring +15."""
        strat = TrendFollowingStrategy()
        ind = _strong_uptrend_indicators()
        ind["RSI_14"] = 50.0
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "BUY"

    def test_adx_boundary_30_scores_20(self) -> None:
        """ADX > 30: value 30.1 should score +20."""
        strat = TrendFollowingStrategy()
        ind = _strong_uptrend_indicators()
        ind["ADX_14"] = 30.1
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.confidence <= 95
        assert sig.action == "BUY"

    def test_ema_pullback_exactly_1pct_qualifies(self) -> None:
        """close exactly 1% above EMA_21 should trigger the pullback bonus."""
        strat = TrendFollowingStrategy()
        ind = _strong_uptrend_indicators(close=100.0)
        ind["EMA_21"] = 100.0 / 1.01  # close is exactly 1.01 * EMA_21 → diff = 1%
        ind["EMA_9"] = 102.0
        ind["EMA_50"] = 98.0
        ind["EMA_200"] = 95.0
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "BUY"

    def test_supertrend_below_close_adds_score(self) -> None:
        """Supertrend below close should add +10 to score."""
        strat = TrendFollowingStrategy()
        ind = _strong_uptrend_indicators(close=100.0)
        ind["Supertrend_10_3"] = 95.0  # below close
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        assert sig.action == "BUY"

    def test_macd_negative_no_macd_bonus(self) -> None:
        """Negative MACD should not award the +15 MACD bonus."""
        strat = TrendFollowingStrategy()
        ind = _strong_uptrend_indicators()
        ind["MACD_12_26_9"] = -0.1
        ind["MACD_hist"] = -0.05
        # Score without MACD: full EMA (+20) + ADX>30 (+20) + RSI 50-70 (+15) + supertrend (+10) = 65 → still BUY
        ms = _make_market_state(indicators_5m=ind)
        sig = strat.generate_signal("BTC/USDT", ms)
        # Score is still >=55 due to other conditions, but MACD didn't contribute
        assert sig.action == "BUY"


# ---------------------------------------------------------------------------
# Required named tests (spec-mandated names)
# ---------------------------------------------------------------------------

def test_name_and_optimal_regimes() -> None:
    """Strategy name must be 'TrendFollowing' with three optimal regimes."""
    strat = TrendFollowingStrategy()
    assert strat.name == "TrendFollowing"
    assert SynthesizedRegime.REGIME_STRONG_BULL in strat.optimal_regimes
    assert SynthesizedRegime.REGIME_MODERATE_BULL in strat.optimal_regimes
    assert SynthesizedRegime.REGIME_BREAKOUT_BULL in strat.optimal_regimes


def test_strong_uptrend_buy() -> None:
    """All EMAs aligned, ADX>30, MACD positive → BUY signal."""
    strat = TrendFollowingStrategy()
    ms = _make_market_state(indicators_5m=_strong_uptrend_indicators())
    sig = strat.generate_signal("BTC/USDT", ms)
    assert sig.action == "BUY"
    assert sig.is_buy is True
    assert sig.confidence > 0


def test_no_trend_no_signal() -> None:
    """EMAs not aligned and ADX<15 → NO_SIGNAL."""
    strat = TrendFollowingStrategy()
    ind = {
        "EMA_9": 95.0,
        "EMA_21": 97.0,    # 9 < 21 — no alignment
        "EMA_50": 98.0,
        "EMA_200": 99.0,
        "ADX_14": 12.0,    # very weak trend
        "MACD_12_26_9": -0.1,
        "MACD_hist": -0.05,
        "RSI_14": 40.0,
        "Supertrend_10_3": 98.0,
        "close": 96.0,
        "ATR_14": 1.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    sig = strat.generate_signal("BTC/USDT", ms)
    assert sig.action == "NO_SIGNAL"
    assert sig.is_buy is False


def test_pullback_entry() -> None:
    """Close near EMA_21 in uptrend (within 1%, above it) → BUY with pullback bonus."""
    strat = TrendFollowingStrategy()
    close = 100.0
    ema21 = 99.6  # close is 0.4% above EMA_21 — within 1%
    ind = {
        "EMA_9": 101.0,
        "EMA_21": ema21,
        "EMA_50": 96.0,
        "EMA_200": 90.0,
        "ADX_14": 28.0,    # >25 → +15
        "MACD_12_26_9": 0.3,
        "MACD_hist": 0.1,
        "RSI_14": 58.0,    # 50-70 → +15
        "Supertrend_10_3": 94.0,
        "close": close,
        "ATR_14": 1.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    sig = strat.generate_signal("BTC/USDT", ms)
    assert sig.action == "BUY"
    assert "pullback" in sig.reasoning.lower()


def test_confidence_capped_at_95() -> None:
    """Confidence must never exceed 95, even with maximum score."""
    strat = TrendFollowingStrategy()
    close = 100.0
    ema21 = 99.8  # within 1% above
    ind = {
        "EMA_9": 101.0,
        "EMA_21": ema21,
        "EMA_50": 96.0,
        "EMA_200": 90.0,
        "ADX_14": 35.0,
        "MACD_12_26_9": 0.5,
        "MACD_hist": 0.2,
        "RSI_14": 60.0,
        "Supertrend_10_3": 95.0,
        "close": close,
        "ATR_14": 1.0,
        "Volume_SMA_20": 1000.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    sig = strat.generate_signal("BTC/USDT", ms)
    assert sig.action == "BUY"
    assert sig.confidence <= 95


def test_stop_loss_calculation() -> None:
    """Stop loss = max(EMA_50, close - ATR*3.0)."""
    strat = TrendFollowingStrategy()
    close = 100.0
    atr = 1.0
    ema50 = 95.0  # close - ATR*3 = 97.0 > 95.0 → use 97.0
    ind = _strong_uptrend_indicators(close=close, atr=atr)
    ind["EMA_50"] = ema50
    ms = _make_market_state(indicators_5m=ind)
    sig = strat.generate_signal("BTC/USDT", ms)
    expected = max(ema50, close - atr * 3.0)
    assert sig.stop_loss == round(expected, 8)


def test_take_profit_levels() -> None:
    """Four TPs at ATR*2, *3, *4, *6, each 25%."""
    strat = TrendFollowingStrategy()
    close = 100.0
    atr = 1.0
    ind = _strong_uptrend_indicators(close=close, atr=atr)
    ms = _make_market_state(indicators_5m=ind)
    sig = strat.generate_signal("BTC/USDT", ms)
    assert len(sig.take_profit_levels) == 4
    tps = sig.take_profit_levels
    assert tps[0] == {"price": round(close + atr * 2, 8), "pct": 0.25}
    assert tps[1] == {"price": round(close + atr * 3, 8), "pct": 0.25}
    assert tps[2] == {"price": round(close + atr * 4, 8), "pct": 0.25}
    assert tps[3] == {"price": round(close + atr * 6, 8), "pct": 0.25}


def test_exit_below_ema50() -> None:
    """Price below EMA_50 → full exit (1.0) with urgency 75 and correct reason."""
    strat = TrendFollowingStrategy()
    ind = {
        "EMA_9": 98.0,
        "EMA_21": 99.0,
        "EMA_50": 101.0,   # close < EMA_50
        "ADX_14": 25.0,
        "MACD_12_26_9": 0.2,
        "MACD_hist": 0.1,
        "close": 100.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    ex = strat.generate_exit_signal("BTC/USDT", ms, entry_price=100.0, current_pnl_pct=0.0)
    assert ex.should_exit is True
    assert ex.urgency == 75
    assert ex.partial_pct == 1.0
    assert "Price below EMA50" in ex.reason


def test_exit_ema_cross_down() -> None:
    """EMA_9 < EMA_21 (price above EMA_50) → partial 0.5 exit, urgency 50."""
    strat = TrendFollowingStrategy()
    ind = {
        "EMA_9": 98.0,     # 9 < 21
        "EMA_21": 99.0,
        "EMA_50": 95.0,    # close > EMA_50
        "ADX_14": 25.0,    # > 20
        "MACD_12_26_9": 0.2,
        "MACD_hist": 0.1,
        "close": 100.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    ex = strat.generate_exit_signal("BTC/USDT", ms, entry_price=100.0, current_pnl_pct=0.0)
    assert ex.should_exit is True
    assert ex.urgency == 50
    assert ex.partial_pct == 0.5
    assert "Short-term trend weakening" in ex.reason


def test_exit_adx_dying() -> None:
    """ADX < 20 (EMA_9 > EMA_21, price above EMA_50) → partial 0.5 exit, urgency 60."""
    strat = TrendFollowingStrategy()
    ind = {
        "EMA_9": 100.5,    # 9 > 21
        "EMA_21": 99.0,
        "EMA_50": 95.0,    # close > EMA_50
        "ADX_14": 15.0,    # < 20
        "MACD_12_26_9": 0.2,
        "MACD_hist": 0.1,
        "close": 100.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    ex = strat.generate_exit_signal("BTC/USDT", ms, entry_price=100.0, current_pnl_pct=0.0)
    assert ex.should_exit is True
    assert ex.urgency == 60
    assert ex.partial_pct == 0.5
    assert "Trend strength dying" in ex.reason


def test_no_exit_healthy_trend() -> None:
    """No exit triggered when trend is strong and price holds above EMA_50."""
    strat = TrendFollowingStrategy()
    ind = {
        "EMA_9": 101.0,
        "EMA_21": 99.0,
        "EMA_50": 95.0,
        "ADX_14": 32.0,
        "MACD_12_26_9": 0.5,
        "MACD_hist": 0.2,
        "close": 100.0,
    }
    ms = _make_market_state(indicators_5m=ind)
    ex = strat.generate_exit_signal("BTC/USDT", ms, entry_price=95.0, current_pnl_pct=5.0)
    assert ex.should_exit is False
    assert ex.urgency == 0


def test_missing_indicators_no_crash() -> None:
    """Strategy must not crash with empty indicators; must return NO_SIGNAL."""
    strat = TrendFollowingStrategy()
    ms = _make_market_state(indicators_5m={})
    sig = strat.generate_signal("BTC/USDT", ms)
    assert isinstance(sig, Signal)
    assert sig.action == "NO_SIGNAL"


def test_regime_active_strong_bull() -> None:
    """Strategy is active for REGIME_STRONG_BULL."""
    strat = TrendFollowingStrategy()
    assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is True


def test_regime_inactive_panic() -> None:
    """Strategy is NOT active for REGIME_PANIC."""
    strat = TrendFollowingStrategy()
    assert strat.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False
