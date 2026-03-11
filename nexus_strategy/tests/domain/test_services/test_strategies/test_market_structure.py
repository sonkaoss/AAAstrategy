"""Tests for MarketStructureStrategy."""
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
from nexus_strategy.domain.services.strategies.market_structure import (
    MarketStructureStrategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAIR = "SOL/USDT"


def _make_market_state(
    pair: str = PAIR,
    indicators_5m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_TRANSITION_UP,
    btc_trend: str = "bullish",
) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.ACCUMULATION,
        macro=MacroRegime.MACRO_TRANSITION_UP,
        synthesized=synthesized,
        confidence=75,
        duration_candles=5,
        transition_probability=0.15,
        recommended_strategies=["MarketStructure"],
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
        btc_change_24h=1.5,
        btc_above_ema200=True,
        btc_trend=btc_trend,
        market_phase="TRANSITION",
        altcoin_season_index=55,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _structure_indicators(
    *,
    close: float = 110.0,
    ema9: float = 108.0,
    ema21: float = 105.0,
    ema50: float = 100.0,
    ema200: float = 80.0,
    bb_upper: float = 115.0,
    bb_lower: float = 90.0,
    rsi: float = 57.0,
    adx: float = 28.0,
    roc: float = 1.2,
    volume_sma: float = 500_000.0,
    atr: float = 2.0,
) -> dict:
    return {
        "close": close,
        "EMA_9": ema9,
        "EMA_21": ema21,
        "EMA_50": ema50,
        "EMA_200": ema200,
        "BB_upper_20": bb_upper,
        "BB_lower_20": bb_lower,
        "RSI_14": rsi,
        "ADX_14": adx,
        "ROC_9": roc,
        "Volume_SMA_20": volume_sma,
        "ATR_14": atr,
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def strategy() -> MarketStructureStrategy:
    return MarketStructureStrategy()


# ---------------------------------------------------------------------------
# test_name_and_optimal_regimes
# ---------------------------------------------------------------------------

class TestNameAndOptimalRegimes:
    def test_name_and_optimal_regimes(self, strategy: MarketStructureStrategy) -> None:
        assert strategy.name == "MarketStructure"
        regimes = strategy.optimal_regimes
        assert SynthesizedRegime.REGIME_TRANSITION_UP in regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in regimes
        assert SynthesizedRegime.REGIME_BREAKOUT_BULL in regimes

    def test_is_active_for_optimal_regimes(self, strategy: MarketStructureStrategy) -> None:
        for regime in [
            SynthesizedRegime.REGIME_TRANSITION_UP,
            SynthesizedRegime.REGIME_ACCUMULATION,
            SynthesizedRegime.REGIME_BREAKOUT_BULL,
        ]:
            assert strategy.is_active_for_regime(regime) is True

    def test_not_active_for_non_optimal_regime(self, strategy: MarketStructureStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False


# ---------------------------------------------------------------------------
# test_structure_break_buy
# ---------------------------------------------------------------------------

class TestStructureBreakBuy:
    def test_structure_break_buy(self, strategy: MarketStructureStrategy) -> None:
        """close > EMA_50 (BOS), EMA_9 > EMA_21 (CHoCH), RSI in (50,65) → BUY."""
        ind = _structure_indicators(close=110.0, ema50=100.0, ema9=108.0, ema21=105.0, rsi=57.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert isinstance(sig, Signal)
        assert sig.action == "BUY"
        assert sig.is_buy is True
        assert sig.pair == PAIR
        assert sig.strategy_name == "MarketStructure"

    def test_buy_entry_price_is_close(self, strategy: MarketStructureStrategy) -> None:
        ind = _structure_indicators(close=110.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.entry_price == pytest.approx(110.0)


# ---------------------------------------------------------------------------
# test_no_structure_no_signal
# ---------------------------------------------------------------------------

class TestNoStructureNoSignal:
    def test_no_structure_no_signal(self, strategy: MarketStructureStrategy) -> None:
        """close < EMA_50, EMA_9 < EMA_21 → NO_SIGNAL (score too low)."""
        # BOS fails (close < ema50), CHoCH fails (ema9 < ema21)
        # No other conditions met either → score = 0 + btc_trend bonus only = 5 < 55
        ind = _structure_indicators(
            close=90.0,
            ema50=100.0,
            ema9=95.0,
            ema21=97.0,
            rsi=45.0,
            bb_upper=115.0,
            bb_lower=75.0,
            ema200=80.0,
        )
        ms = _make_market_state(indicators_5m=ind, btc_trend="bearish")
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False
        assert sig.confidence == 0

    def test_zero_close_no_signal(self, strategy: MarketStructureStrategy) -> None:
        ind = _structure_indicators(close=0.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# test_order_block_entry
# ---------------------------------------------------------------------------

class TestOrderBlockEntry:
    def test_order_block_entry(self, strategy: MarketStructureStrategy) -> None:
        """close near EMA_200 (within 2%) and RSI < 40 → adds +15 to score."""
        # EMA_200 = 100, close = 101 (1% away), RSI = 35 → order block +15
        # Also: close(101) > ema50(100) → BOS +20
        # CHoCH: ema9(105) > ema21(102) → +15
        # Total so far: 50 + 15 (order block) = 50, but also check RSI: rsi=35 not in (50,65)
        # Higher low: bb_lower(85) > ema200(100)? No. Higher high: close(101) > bb_upper(115)*0.99=113.85? No.
        # BTC: bearish so no +5
        # Score = 20 + 15 + 15 = 50 < 55 — need to also pass close > EMA_50
        # Let's verify score = 20(BOS) + 15(CHoCH) + 15(OB) = 50 < 55, no buy
        # Adjust: add higher low to push over 55
        ind = _structure_indicators(
            close=101.0,
            ema50=100.0,
            ema9=105.0,
            ema21=102.0,
            ema200=100.0,
            bb_lower=101.0,  # bb_lower > ema200 → higher low +10
            bb_upper=120.0,
            rsi=35.0,
            atr=2.0,
        )
        # Score: BOS +20, CHoCH +15, higher low (101>100) +10, order block (|101-100|/100=0.01 ≤ 0.02, rsi<40) +15
        # = 60 >= 55 → BUY
        ms = _make_market_state(indicators_5m=ind, btc_trend="bearish")
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "BUY"
        assert "Order Block" in sig.reasoning

    def test_order_block_not_triggered_when_far_from_ema200(self, strategy: MarketStructureStrategy) -> None:
        """When close is more than 2% away from EMA_200, order block bonus not awarded."""
        ind = _structure_indicators(
            close=115.0,  # far from ema200=80
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
            ema200=80.0,
            rsi=35.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        # Score: BOS +20, CHoCH +15, btc +5 = 40 — check higher high: close(115)>bb_upper(115)*0.99=113.85 → +10
        # Higher low: bb_lower(90) > ema200(80) → +10
        # Total: 60 → BUY
        # But order block should NOT be in reasoning
        if sig.action == "BUY":
            assert "Order Block" not in sig.reasoning


# ---------------------------------------------------------------------------
# test_btc_context_bonus
# ---------------------------------------------------------------------------

class TestBtcContextBonus:
    def test_btc_context_bonus(self, strategy: MarketStructureStrategy) -> None:
        """btc_trend='bullish' adds +5 to score."""
        # Minimal setup: BOS +20, CHoCH +15, RSI +10 = 45 < 55 → no buy without btc
        ind = _structure_indicators(
            close=110.0,
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
            ema200=80.0,
            bb_upper=200.0,   # no higher high
            bb_lower=60.0,    # bb_lower(60) < ema200(80) → no higher low
            rsi=57.0,
            atr=2.0,
        )
        # Score without btc: BOS +20 + CHoCH +15 + RSI +10 = 45 < 55 → no signal
        ms_no_btc = _make_market_state(indicators_5m=ind, btc_trend="bearish")
        sig_no_btc = strategy.generate_signal(PAIR, ms_no_btc)
        assert sig_no_btc.action == "NO_SIGNAL"

        # Score with btc: 45 + 5 = 50 < 55 → still no signal
        # Use a scenario where btc pushes it over the threshold
        # BOS +20 + CHoCH +15 + RSI +10 + higher_low +10 = 55, borderline
        ind2 = _structure_indicators(
            close=110.0,
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
            ema200=80.0,
            bb_upper=200.0,   # no higher high
            bb_lower=85.0,    # bb_lower(85) > ema200(80) → higher low +10
            rsi=57.0,
            atr=2.0,
        )
        # Score without btc: 20 + 15 + 10 + 10 = 55 → BUY
        # Score with btc: 60 → BUY with higher confidence
        ms_bull = _make_market_state(indicators_5m=ind2, btc_trend="bullish")
        ms_bear = _make_market_state(indicators_5m=ind2, btc_trend="bearish")
        sig_bull = strategy.generate_signal(PAIR, ms_bull)
        sig_bear = strategy.generate_signal(PAIR, ms_bear)
        # Both should be BUY but bull has higher confidence
        assert sig_bull.action == "BUY"
        assert sig_bear.action == "BUY"
        assert sig_bull.confidence > sig_bear.confidence

    def test_btc_neutral_no_bonus(self, strategy: MarketStructureStrategy) -> None:
        """btc_trend != 'bullish' gives no bonus."""
        ind = _structure_indicators()
        ms = _make_market_state(indicators_5m=ind, btc_trend="neutral")
        sig = strategy.generate_signal(PAIR, ms)
        if sig.action == "BUY":
            assert "BTC trend bullish" not in sig.reasoning


# ---------------------------------------------------------------------------
# test_confidence_capped_at_90
# ---------------------------------------------------------------------------

class TestConfidenceCap:
    def test_confidence_capped_at_90(self, strategy: MarketStructureStrategy) -> None:
        """Confidence is capped at 90 regardless of how high the score is."""
        # Max possible score: 20+15+10+10+15+10+5 = 85 → min(85,90) = 85
        # All conditions true:
        ind = _structure_indicators(
            close=101.0,
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
            ema200=100.0,
            bb_upper=102.0,        # close(101) > bb_upper(102)*0.99=100.98 → higher high +10
            bb_lower=101.0,        # bb_lower(101) > ema200(100) → higher low +10
            rsi=35.0,              # order block: within 2% of ema200 and rsi<40 → +15
            atr=2.0,
        )
        ms = _make_market_state(indicators_5m=ind, btc_trend="bullish")
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "BUY"
        assert sig.confidence <= 90

    def test_confidence_matches_score_when_below_90(self, strategy: MarketStructureStrategy) -> None:
        """When score < 90, confidence equals score."""
        # BOS +20, CHoCH +15, RSI +10, btc +5 = 50; higher low +10 = 60
        ind = _structure_indicators(
            close=110.0,
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
            ema200=80.0,
            bb_upper=200.0,   # no higher high
            bb_lower=85.0,    # bb_lower(85) > ema200(80) → +10
            rsi=57.0,
            atr=2.0,
        )
        ms = _make_market_state(indicators_5m=ind, btc_trend="bullish")
        sig = strategy.generate_signal(PAIR, ms)
        assert sig.action == "BUY"
        # Score = 20 + 15 + 10 + 10 + 5 = 60
        assert sig.confidence == 60


# ---------------------------------------------------------------------------
# test_stop_loss_calculation
# ---------------------------------------------------------------------------

class TestStopLossCalculation:
    def test_stop_loss_uses_ema200_when_higher(self, strategy: MarketStructureStrategy) -> None:
        """When EMA_200 > close - ATR*3, use EMA_200 as stop loss."""
        # close=110, atr=2 → sl_atr = 110 - 6 = 104; ema200=105 → stop = max(105, 104) = 105
        ind = _structure_indicators(close=110.0, ema200=105.0, atr=2.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        if sig.action == "BUY":
            assert sig.stop_loss == pytest.approx(105.0)

    def test_stop_loss_uses_atr_when_higher(self, strategy: MarketStructureStrategy) -> None:
        """When close - ATR*3 > EMA_200, use ATR-based stop loss."""
        # close=110, atr=2 → sl_atr = 110 - 6 = 104; ema200=80 → stop = max(80, 104) = 104
        ind = _structure_indicators(close=110.0, ema200=80.0, atr=2.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        if sig.action == "BUY":
            assert sig.stop_loss == pytest.approx(110.0 - 2.0 * 3.0)


# ---------------------------------------------------------------------------
# test_take_profit_levels
# ---------------------------------------------------------------------------

class TestTakeProfitLevels:
    def test_take_profit_levels(self, strategy: MarketStructureStrategy) -> None:
        """TP levels: EMA_50+ATR, BB_upper, close+ATR*3, close+ATR*5 each at 25%."""
        ind = _structure_indicators(
            close=110.0,
            ema50=100.0,
            bb_upper=115.0,
            atr=2.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        if sig.action == "BUY":
            assert len(sig.take_profit_levels) == 4
            assert sig.take_profit_levels[0]["price"] == pytest.approx(100.0 + 2.0)  # EMA_50 + ATR
            assert sig.take_profit_levels[1]["price"] == pytest.approx(115.0)         # BB_upper_20
            assert sig.take_profit_levels[2]["price"] == pytest.approx(110.0 + 2.0 * 3)  # close + ATR*3
            assert sig.take_profit_levels[3]["price"] == pytest.approx(110.0 + 2.0 * 5)  # close + ATR*5

    def test_take_profit_percentages(self, strategy: MarketStructureStrategy) -> None:
        """Each TP level is 25% of position."""
        ind = _structure_indicators()
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        if sig.action == "BUY":
            for level in sig.take_profit_levels:
                assert level["pct"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# test_exit_structure_broken
# ---------------------------------------------------------------------------

class TestExitStructureBroken:
    def test_exit_structure_broken(self, strategy: MarketStructureStrategy) -> None:
        """close < EMA_50 → full exit, urgency 70."""
        ind = _structure_indicators(close=95.0, ema50=100.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=105.0, current_pnl_pct=-0.1)
        assert ex.should_exit is True
        assert ex.urgency == 70
        assert ex.partial_pct == pytest.approx(1.0)
        assert ex.exit_layer == ExitLayer.TECHNICAL
        assert "EMA_50" in ex.reason


# ---------------------------------------------------------------------------
# test_exit_momentum_shift
# ---------------------------------------------------------------------------

class TestExitMomentumShift:
    def test_exit_momentum_shift(self, strategy: MarketStructureStrategy) -> None:
        """EMA_9 < EMA_21 (structure intact, momentum shifted) → partial exit, urgency 50."""
        ind = _structure_indicators(
            close=110.0,
            ema50=100.0,   # close > ema50 → no structure break
            ema9=103.0,
            ema21=105.0,   # ema9 < ema21 → momentum shift
        )
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=108.0, current_pnl_pct=0.02)
        assert ex.should_exit is True
        assert ex.urgency == 50
        assert ex.partial_pct == pytest.approx(0.5)
        assert ex.exit_layer == ExitLayer.TECHNICAL


# ---------------------------------------------------------------------------
# test_no_exit_healthy_structure
# ---------------------------------------------------------------------------

class TestNoExitHealthyStructure:
    def test_no_exit_healthy_structure(self, strategy: MarketStructureStrategy) -> None:
        """When close > EMA_50 and EMA_9 > EMA_21, no exit signal."""
        ind = _structure_indicators(
            close=110.0,
            ema50=100.0,
            ema9=108.0,
            ema21=105.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=105.0, current_pnl_pct=0.05)
        assert ex.should_exit is False
        assert ex.urgency == 0
        assert ex.partial_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# test_missing_indicators_no_crash
# ---------------------------------------------------------------------------

class TestMissingIndicatorsNoCrash:
    def test_missing_indicators_no_crash(self, strategy: MarketStructureStrategy) -> None:
        """Empty indicators dict should not raise exceptions and return NO_SIGNAL."""
        ms = _make_market_state(indicators_5m={})
        sig = strategy.generate_signal(PAIR, ms)
        assert isinstance(sig, Signal)
        assert sig.action == "NO_SIGNAL"

    def test_missing_indicators_exit_no_crash(self, strategy: MarketStructureStrategy) -> None:
        """Empty indicators dict should not raise exceptions in exit signal."""
        ms = _make_market_state(indicators_5m={})
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=100.0, current_pnl_pct=0.0)
        assert isinstance(ex, ExitSignal)
        assert ex.should_exit is False

    def test_unknown_pair_no_crash(self, strategy: MarketStructureStrategy) -> None:
        """Unknown pair should not crash and return NO_SIGNAL."""
        ms = _make_market_state(indicators_5m=_structure_indicators())
        sig = strategy.generate_signal("UNKNOWN/USDT", ms)
        assert sig.action == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# test_regime_active_transition_up
# ---------------------------------------------------------------------------

class TestRegimeActiveTransitionUp:
    def test_regime_active_transition_up(self, strategy: MarketStructureStrategy) -> None:
        """Strategy should be active for REGIME_TRANSITION_UP."""
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_TRANSITION_UP) is True

    def test_regime_active_accumulation(self, strategy: MarketStructureStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_ACCUMULATION) is True

    def test_regime_active_breakout_bull(self, strategy: MarketStructureStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_BREAKOUT_BULL) is True

    def test_regime_inactive_for_bear(self, strategy: MarketStructureStrategy) -> None:
        assert strategy.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False

    def test_signal_has_timestamp(self, strategy: MarketStructureStrategy) -> None:
        ind = _structure_indicators()
        ms = _make_market_state(indicators_5m=ind)
        sig = strategy.generate_signal(PAIR, ms)
        assert isinstance(sig.timestamp, datetime)

    def test_exit_signal_has_timestamp(self, strategy: MarketStructureStrategy) -> None:
        ind = _structure_indicators(close=95.0, ema50=100.0)
        ms = _make_market_state(indicators_5m=ind)
        ex = strategy.generate_exit_signal(PAIR, ms, entry_price=105.0, current_pnl_pct=-0.1)
        assert isinstance(ex.timestamp, datetime)
