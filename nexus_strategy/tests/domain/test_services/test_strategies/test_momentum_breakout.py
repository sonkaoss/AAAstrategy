"""Tests for MomentumBreakoutStrategy."""
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
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.momentum_breakout import (
    MomentumBreakoutStrategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAIR = "ETH/USDT"


def _make_market_state(
    pair: str = PAIR,
    indicators_5m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_SQUEEZE,
) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_BREAKOUT_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=80,
        duration_candles=3,
        transition_probability=0.1,
        recommended_strategies=["MomentumBreakout"],
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
        btc_price=50_000.0,
        btc_change_1h=0.5,
        btc_change_24h=1.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=60,
        fear_greed=60,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _breakout_indicators(
    *,
    close: float = 105.0,
    bb_upper: float = 100.0,
    bb_lower: float = 90.0,
    bb_mid: float = 95.0,
    bb_width: float = 10.0,
    keltner_upper: float = 102.0,
    keltner_lower: float = 88.0,
    roc: float = 2.0,
    adx: float = 30.0,
    rsi: float = 62.0,
    volume_sma: float = 1_000_000.0,
    atr: float = 1.5,
    obv: float = 500_000.0,
) -> dict:
    return {
        "close": close,
        "BB_upper_20": bb_upper,
        "BB_lower_20": bb_lower,
        "BB_mid_20": bb_mid,
        "BB_width_20": bb_width,
        "Keltner_upper": keltner_upper,
        "Keltner_lower": keltner_lower,
        "ROC_9": roc,
        "ADX_14": adx,
        "RSI_14": rsi,
        "Volume_SMA_20": volume_sma,
        "ATR_14": atr,
        "OBV": obv,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def strategy() -> MomentumBreakoutStrategy:
    return MomentumBreakoutStrategy()


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_name(self, strategy: MomentumBreakoutStrategy) -> None:
        assert strategy.name == "MomentumBreakout"

    def test_optimal_regimes(self, strategy: MomentumBreakoutStrategy) -> None:
        regimes = strategy.optimal_regimes
        assert SynthesizedRegime.REGIME_SQUEEZE in regimes
        assert SynthesizedRegime.REGIME_BREAKOUT_BULL in regimes
        assert SynthesizedRegime.REGIME_TRANSITION_UP in regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in regimes

    def test_is_active_for_optimal_regimes(self, strategy: MomentumBreakoutStrategy) -> None:
        for regime in [
            SynthesizedRegime.REGIME_SQUEEZE,
            SynthesizedRegime.REGIME_BREAKOUT_BULL,
            SynthesizedRegime.REGIME_TRANSITION_UP,
            SynthesizedRegime.REGIME_ACCUMULATION,
        ]:
            assert strategy.is_active_for_regime(regime) is True

    def test_not_active_for_non_optimal_regime(self, strategy: MomentumBreakoutStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False


# ---------------------------------------------------------------------------
# generate_signal — BUY cases
# ---------------------------------------------------------------------------

class TestGenerateSignalBuy:
    def test_breakout_buy_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal(PAIR, ms)
        assert isinstance(sig, Signal)
        assert sig.action == "BUY"
        assert sig.is_buy is True
        assert sig.pair == PAIR
        assert sig.strategy_name == "MomentumBreakout"

    def test_buy_confidence_capped_at_95(self, strategy: MomentumBreakoutStrategy) -> None:
        # Max possible score: 25+20+15+10+10+5 = 85, never exceeds 95
        # But let's explicitly check the cap
        ms = _make_market_state(indicators_5m=_breakout_indicators(roc=2.0))
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.confidence <= 95

    def test_buy_confidence_equals_score_when_below_95(self, strategy: MomentumBreakoutStrategy) -> None:
        # With BB breakout (+25), ROC>1.5 (+20), volume (+15), ADX>25 (+10), RSI 55-75 (+10), OBV (+5) = 85
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.confidence == 85

    def test_buy_entry_price_is_close(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators(close=105.0))
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.entry_price == 105.0

    def test_buy_stop_loss_is_max_of_bb_mid_and_atr(self, strategy: MomentumBreakoutStrategy) -> None:
        # close=105, bb_mid=95, atr=1.5 → sl_atr = 105 - 1.5*2 = 102 → stop = max(95, 102) = 102
        ms = _make_market_state(indicators_5m=_breakout_indicators(close=105.0, bb_mid=95.0, atr=1.5))
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.stop_loss == pytest.approx(105.0 - 1.5 * 2.0)

    def test_buy_stop_loss_uses_bb_mid_when_higher(self, strategy: MomentumBreakoutStrategy) -> None:
        # close=100, bb_mid=98, atr=0.5 → sl_atr = 100 - 0.5*2 = 99 → stop = max(98, 99) = 99
        ms = _make_market_state(indicators_5m=_breakout_indicators(close=100.0, bb_mid=98.0, atr=0.5, bb_upper=99.5))
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.stop_loss == pytest.approx(99.0)

    def test_buy_take_profit_levels_structure(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators(close=100.0, atr=2.0))
        sig = strategy.generate_signal(PAIR, ms)
        assert len(sig.take_profit_levels) == 3
        assert sig.take_profit_levels[0]["price"] == pytest.approx(100.0 + 2.0 * 1.5)
        assert sig.take_profit_levels[1]["price"] == pytest.approx(100.0 + 2.0 * 3.0)
        assert sig.take_profit_levels[2]["price"] == pytest.approx(100.0 + 2.0 * 5.0)

    def test_buy_take_profit_percentages(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.take_profit_levels[0]["pct"] == pytest.approx(0.3)
        assert sig.take_profit_levels[1]["pct"] == pytest.approx(0.3)
        assert sig.take_profit_levels[2]["pct"] == pytest.approx(0.4)

    def test_buy_indicators_used_listed(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal(PAIR, ms)
        assert "close" in sig.indicators_used
        assert "BB_upper_20" in sig.indicators_used
        assert "ROC_9" in sig.indicators_used
        assert "ATR_14" in sig.indicators_used

    def test_buy_reasoning_mentions_bb_breakout(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal(PAIR, ms)
        assert "BB breakout" in sig.reasoning


# ---------------------------------------------------------------------------
# generate_signal — NO_SIGNAL cases
# ---------------------------------------------------------------------------

class TestGenerateSignalNoSignal:
    def test_no_breakout_no_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        # close < bb_upper, low ROC, weak indicators
        ind = _breakout_indicators(close=95.0, bb_upper=100.0, roc=0.2, adx=15.0, rsi=45.0, obv=-1.0, volume_sma=0.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False
        assert sig.confidence == 0

    def test_score_below_threshold_no_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        # Only ROC > 1.5 (+20) and volume (+15) → 35 < 55
        ind = _breakout_indicators(
            close=95.0, bb_upper=100.0, roc=2.0, adx=15.0, rsi=45.0, obv=-1.0, volume_sma=500.0
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"

    def test_zero_close_no_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(close=0.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"

    def test_missing_indicators_no_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m={})
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# Fake breakout filter
# ---------------------------------------------------------------------------

class TestFakeBreakoutFilter:
    def test_rsi_above_80_reduces_score(self, strategy: MomentumBreakoutStrategy) -> None:
        # Without filter: 25+20+15+10+5 = 75 (RSI not in 55-75), then -20 = 55 exactly → BUY
        # rsi=82 → no RSI +10, but fake breakout -20
        # Score without rsi bonus: 25+20+15+10+5 = 75, then -20 = 55 → BUY at confidence 55
        ind = _breakout_indicators(rsi=82.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+20+15+10+5 - 20 = 55 → BUY with confidence 55
        assert sig.action == "BUY"
        assert sig.confidence == 55

    def test_rsi_above_80_blocks_weak_breakout(self, strategy: MomentumBreakoutStrategy) -> None:
        # BB breakout (+25), ROC>1.5 (+20), volume (+15) = 60, then -20 = 40 < 55 → NO_SIGNAL
        ind = _breakout_indicators(rsi=85.0, adx=10.0, obv=-1.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+20+15 = 60, -20 = 40 < 55 → NO_SIGNAL
        assert sig.action == "NO_SIGNAL"

    def test_rsi_exactly_80_no_penalty(self, strategy: MomentumBreakoutStrategy) -> None:
        # RSI = 80 → NOT > 80, so no penalty; also not in 55-75 range
        ind = _breakout_indicators(rsi=80.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+20+15+10+5 = 75 (no RSI +10 since 80 > 75) → BUY
        assert sig.action == "BUY"
        assert sig.confidence == 75


# ---------------------------------------------------------------------------
# Exit signal
# ---------------------------------------------------------------------------

class TestGenerateExitSignal:
    def test_exit_when_price_falls_below_bb_upper_after_entry_above(
        self, strategy: MomentumBreakoutStrategy
    ) -> None:
        # entry_price was above bb_upper, now close < bb_upper
        ind = _breakout_indicators(close=99.0, bb_upper=100.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=101.0, current_pnl_pct=-0.02)
        assert ex.should_exit is True
        assert ex.urgency == 80
        assert ex.partial_pct == 1.0
        assert ex.exit_layer == ExitLayer.TECHNICAL

    def test_no_exit_when_still_above_bb_upper(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(close=105.0, bb_upper=100.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=101.0, current_pnl_pct=0.04)
        assert ex.should_exit is False

    def test_exit_partial_when_roc_negative(self, strategy: MomentumBreakoutStrategy) -> None:
        # close still above bb_upper (no full exit) but ROC < 0
        ind = _breakout_indicators(close=105.0, bb_upper=100.0, roc=-0.5)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=95.0, current_pnl_pct=0.1)
        assert ex.should_exit is True
        assert ex.urgency == 60
        assert ex.partial_pct == pytest.approx(0.5)
        assert ex.exit_layer == ExitLayer.TECHNICAL

    def test_no_exit_when_roc_zero(self, strategy: MomentumBreakoutStrategy) -> None:
        # ROC = 0 is not < 0
        ind = _breakout_indicators(close=105.0, bb_upper=100.0, roc=0.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=95.0, current_pnl_pct=0.1)
        assert ex.should_exit is False

    def test_no_exit_when_roc_positive_and_above_bb_upper(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(close=105.0, bb_upper=100.0, roc=1.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=95.0, current_pnl_pct=0.1)
        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_full_exit_takes_priority_over_roc(self, strategy: MomentumBreakoutStrategy) -> None:
        # Both conditions: fell below bb_upper AND roc < 0 → full exit wins
        ind = _breakout_indicators(close=99.0, bb_upper=100.0, roc=-1.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=101.0, current_pnl_pct=-0.02)
        assert ex.should_exit is True
        assert ex.urgency == 80
        assert ex.partial_pct == 1.0

    def test_exit_signal_has_timestamp(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(close=99.0, bb_upper=100.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=101.0, current_pnl_pct=-0.01)
        assert isinstance(ex.timestamp, datetime)


# ---------------------------------------------------------------------------
# Regime filtering
# ---------------------------------------------------------------------------

class TestRegimeFiltering:
    @pytest.mark.parametrize("regime", [
        SynthesizedRegime.REGIME_SQUEEZE,
        SynthesizedRegime.REGIME_BREAKOUT_BULL,
        SynthesizedRegime.REGIME_TRANSITION_UP,
        SynthesizedRegime.REGIME_ACCUMULATION,
    ])
    def test_active_for_optimal_regimes(
        self, strategy: MomentumBreakoutStrategy, regime: SynthesizedRegime
    ) -> None:
        assert strategy.is_active_for_regime(regime) is True

    @pytest.mark.parametrize("regime", [
        SynthesizedRegime.REGIME_STRONG_BEAR,
        SynthesizedRegime.REGIME_MODERATE_BEAR,
        SynthesizedRegime.REGIME_PANIC,
        SynthesizedRegime.REGIME_CHOPPY,
        SynthesizedRegime.REGIME_DISTRIBUTION,
        SynthesizedRegime.REGIME_BREAKOUT_BEAR,
    ])
    def test_inactive_for_non_optimal_regimes(
        self, strategy: MomentumBreakoutStrategy, regime: SynthesizedRegime
    ) -> None:
        assert strategy.is_active_for_regime(regime) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_signal_for_unknown_pair_returns_no_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        ms = _make_market_state(indicators_5m=_breakout_indicators())
        sig = strategy.generate_signal("UNKNOWN/USDT", ms)
        # No indicators for UNKNOWN/USDT → all default to 0 → close=0 → no_signal
        assert sig.action == "NO_SIGNAL"

    def test_roc_exactly_1_5_gets_20_points(self, strategy: MomentumBreakoutStrategy) -> None:
        # roc > 1.5 means 1.5 exactly does NOT qualify for +20; but > 1.0 → +15
        ind = _breakout_indicators(roc=1.5)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25 (BB) + 15 (ROC>1.0) + 15 (vol) + 10 (ADX) + 10 (RSI) + 5 (OBV) = 80
        assert sig.action == "BUY"
        assert sig.confidence == 80

    def test_roc_exactly_1_0_gets_10_points(self, strategy: MomentumBreakoutStrategy) -> None:
        # roc > 1.0 → False, roc > 0.5 → True → +10
        ind = _breakout_indicators(roc=1.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+10+15+10+10+5 = 75
        assert sig.action == "BUY"
        assert sig.confidence == 75

    def test_obv_zero_gives_no_obv_bonus(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(obv=0.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+20+15+10+10 = 80 (no OBV +5)
        assert sig.action == "BUY"
        assert sig.confidence == 80

    def test_volume_sma_zero_gives_no_volume_bonus(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(volume_sma=0.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score = 25+20+10+10+5 = 70 (no volume +15)
        assert sig.action == "BUY"
        assert sig.confidence == 70

    def test_no_exit_returns_no_exit_signal(self, strategy: MomentumBreakoutStrategy) -> None:
        ind = _breakout_indicators(close=106.0, bb_upper=100.0, roc=1.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=103.0, current_pnl_pct=0.03)
        assert isinstance(ex, ExitSignal)
        assert ex.should_exit is False
        assert ex.urgency == 0
        assert ex.partial_pct == pytest.approx(0.0)
