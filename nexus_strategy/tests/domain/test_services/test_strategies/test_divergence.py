"""Tests for DivergenceStrategy."""
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
from nexus_strategy.domain.services.strategies.divergence import DivergenceStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAIR = "ETH/USDT"


def _make_regime(synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_WEAK_BEAR) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_DOWN,
        mid=MidRegime.TREND_BEAR_WEAK,
        macro=MacroRegime.MACRO_BEAR_EARLY,
        synthesized=synthesized,
        confidence=60,
        duration_candles=12,
        transition_probability=0.2,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )


def _make_market_state(
    pair: str = _PAIR,
    indicators_5m: dict | None = None,
    indicators_15m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_WEAK_BEAR,
) -> MarketState:
    ind_5m = indicators_5m or {}
    ind_15m = indicators_15m or {}
    regime = _make_regime(synthesized)
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
        btc_price=45000.0,
        btc_change_1h=-0.3,
        btc_change_24h=-1.5,
        btc_above_ema200=False,
        btc_trend="bearish",
        market_phase="BEAR",
        altcoin_season_index=30,
        fear_greed=30,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _divergent_indicators(
    close: float = 90.0,
    ema_21: float = 100.0,
    ema_50: float = 110.0,
    rsi: float = 45.0,
    macd: float = 0.5,
    macd_hist: float = 0.1,
    cci: float = -30.0,
    mfi: float = 45.0,
    cmf: float = 0.05,
    bb_lower: float = 95.0,
    bb_upper: float = 115.0,
    atr: float = 2.0,
) -> dict:
    """Build an indicator dict exhibiting bullish divergence conditions."""
    return {
        "close": close,
        "EMA_21": ema_21,
        "EMA_50": ema_50,
        "RSI_14": rsi,
        "MACD_12_26_9": macd,
        "MACDh_12_26_9": macd_hist,
        "CCI_20": cci,
        "MFI_14": mfi,
        "CMF_20": cmf,
        "BB_lower_20": bb_lower,
        "BB_upper_20": bb_upper,
        "ATR_14": atr,
    }


def _aligned_indicators(
    close: float = 110.0,
    ema_21: float = 100.0,
    ema_50: float = 95.0,
    rsi: float = 60.0,
    macd: float = -0.5,
    macd_hist: float = -0.1,
    cci: float = 20.0,
    mfi: float = 55.0,
    cmf: float = -0.05,
    bb_lower: float = 90.0,
    bb_upper: float = 120.0,
    atr: float = 2.0,
) -> dict:
    """Build an indicator dict with no divergence (price above EMAs, oscillators neutral)."""
    return {
        "close": close,
        "EMA_21": ema_21,
        "EMA_50": ema_50,
        "RSI_14": rsi,
        "MACD_12_26_9": macd,
        "MACDh_12_26_9": macd_hist,
        "CCI_20": cci,
        "MFI_14": mfi,
        "CMF_20": cmf,
        "BB_lower_20": bb_lower,
        "BB_upper_20": bb_upper,
        "ATR_14": atr,
    }


# ---------------------------------------------------------------------------
# Strategy setup
# ---------------------------------------------------------------------------

class TestDivergenceStrategySetup:
    def test_name_and_optimal_regimes(self) -> None:
        strat = DivergenceStrategy()
        assert strat.name == "Divergence"
        regimes = strat.optimal_regimes
        assert SynthesizedRegime.REGIME_WEAK_BEAR in regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in regimes
        assert SynthesizedRegime.REGIME_TRANSITION_UP in regimes

    def test_regime_active_weak_bear(self) -> None:
        strat = DivergenceStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_WEAK_BEAR) is True

    def test_regime_active_accumulation(self) -> None:
        strat = DivergenceStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_ACCUMULATION) is True

    def test_regime_active_transition_up(self) -> None:
        strat = DivergenceStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_TRANSITION_UP) is True

    def test_regime_inactive_strong_bull(self) -> None:
        strat = DivergenceStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is False

    def test_regime_inactive_strong_bear(self) -> None:
        strat = DivergenceStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False


# ---------------------------------------------------------------------------
# generate_signal — BUY conditions
# ---------------------------------------------------------------------------

class TestGenerateSignalBuy:
    def setup_method(self) -> None:
        self.strat = DivergenceStrategy()

    def test_bullish_divergence_buy(self) -> None:
        """close < EMA_21, RSI > 40, MACD > 0, CMF > 0 → BUY."""
        # rsi_div: close < ema_21 and rsi > 40 = +20
        # macd_div: close < ema_21 and macd > 0 = +20
        # volume_div: cmf > 0 and close < ema_50 = +15
        # mfi_div: mfi > 40 and close < ema_21 = +10
        # total = 65 >= 50 → BUY
        ind = _divergent_indicators(
            close=90.0, ema_21=100.0, ema_50=110.0,
            rsi=45.0, macd=0.5, macd_hist=0.1,
            cmf=0.05, cci=20.0, mfi=45.0,
            bb_lower=95.0, bb_upper=115.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert sig.is_buy is True

    def test_no_divergence_no_signal(self) -> None:
        """close > EMA_21, oscillators neutral → NO_SIGNAL."""
        ind = _aligned_indicators(
            close=110.0, ema_21=100.0, ema_50=95.0,
            rsi=60.0, macd=-0.5, macd_hist=-0.1,
            cmf=-0.05, cci=20.0, mfi=55.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False

    def test_multi_tf_confirmation_boosts_score(self) -> None:
        """Same divergences on 5m and 15m multiply total score by 1.3."""
        # rsi_div (+20) + macd_div (+20) + volume_div (+15) + mfi_div (+10) = 65
        # Two matching TFs (all 4 divergences match) → 65 * 1.3 = 84
        ind = _divergent_indicators(
            close=90.0, ema_21=100.0, ema_50=110.0,
            rsi=45.0, macd=0.5, macd_hist=0.1,
            cmf=0.05, cci=20.0, mfi=45.0,
            bb_lower=95.0, bb_upper=115.0,
        )
        ms_single = _make_market_state(indicators_5m=ind)
        sig_single = self.strat.generate_signal(_PAIR, ms_single)

        ms_multi = _make_market_state(indicators_5m=ind, indicators_15m=ind)
        sig_multi = self.strat.generate_signal(_PAIR, ms_multi)

        # Both should be BUY but multi-TF should have higher or equal confidence
        assert sig_single.action == "BUY"
        assert sig_multi.action == "BUY"
        assert sig_multi.confidence >= sig_single.confidence

    def test_confidence_capped_at_90(self) -> None:
        """Confidence is capped at 90 regardless of how high the score is."""
        # rsi_div +20, macd_div +20, volume_div +15, cci_div +15, mfi_div +10 = 80
        # with 5+ TF matches * 1.3 = 104 → capped at 90
        ind = _divergent_indicators(
            close=90.0, ema_21=100.0, ema_50=110.0,
            rsi=45.0, macd=0.5, macd_hist=0.1,
            cmf=0.05, cci=-30.0, mfi=45.0,
            bb_lower=95.0, bb_upper=115.0,
        )
        ms = _make_market_state(indicators_5m=ind, indicators_15m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert sig.confidence <= 90

    def test_stop_loss_calculation(self) -> None:
        """Stop loss = close - ATR * 2.5."""
        close = 100.0
        atr = 4.0
        ind = _divergent_indicators(close=close, atr=atr, ema_21=110.0, ema_50=120.0,
                                    rsi=45.0, macd=0.5, cmf=0.05, mfi=45.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        expected_sl = close - atr * 2.5
        assert abs(sig.stop_loss - expected_sl) < 1e-9

    def test_take_profit_levels(self) -> None:
        """Take profit has 3 levels targeting EMA_21, EMA_50 and BB mid."""
        close = 90.0
        ema_21 = 100.0
        ema_50 = 110.0
        bb_lower = 88.0
        bb_upper = 112.0
        ind = _divergent_indicators(
            close=close, ema_21=ema_21, ema_50=ema_50,
            bb_lower=bb_lower, bb_upper=bb_upper,
            rsi=45.0, macd=0.5, cmf=0.05, mfi=45.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert len(sig.take_profit_levels) == 3
        prices = [tp["price"] for tp in sig.take_profit_levels]
        pcts = [tp["pct"] for tp in sig.take_profit_levels]
        assert prices[0] == ema_21
        assert prices[1] == ema_50
        expected_bb_mid = bb_lower + (bb_upper - bb_lower) * 0.5
        assert abs(prices[2] - expected_bb_mid) < 1e-9
        assert abs(pcts[0] - 0.3) < 1e-9
        assert abs(pcts[1] - 0.3) < 1e-9
        assert abs(pcts[2] - 0.4) < 1e-9

    def test_missing_indicators_no_crash(self) -> None:
        """Strategy should return NO_SIGNAL gracefully when indicators are absent."""
        ms = _make_market_state(indicators_5m={}, indicators_15m={})
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "NO_SIGNAL"

    def test_entry_price_is_close(self) -> None:
        close = 88.88
        ind = _divergent_indicators(close=close, ema_21=100.0, ema_50=110.0,
                                    rsi=45.0, macd=0.5, cmf=0.05, mfi=45.0)
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert sig.entry_price == close

    def test_strategy_name_in_signal(self) -> None:
        ind = _divergent_indicators()
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.strategy_name == "Divergence"


# ---------------------------------------------------------------------------
# generate_exit_signal
# ---------------------------------------------------------------------------

class TestGenerateExitSignal:
    def setup_method(self) -> None:
        self.strat = DivergenceStrategy()

    def test_exit_divergence_resolved(self) -> None:
        """RSI > 65 and close > EMA_50 → partial exit, urgency 50."""
        ind_5m = {
            "RSI_14": 70.0,
            "close": 115.0,
            "EMA_50": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=100.0, current_pnl_pct=5.0)
        assert ex.should_exit is True
        assert ex.urgency == 50
        assert ex.partial_pct == 0.5

    def test_exit_stop_loss_hit(self) -> None:
        """close 3%+ below entry_price → full exit, urgency 80."""
        entry_price = 100.0
        close = entry_price * 0.96  # 4% below — triggers stop loss
        ind_5m = {
            "RSI_14": 40.0,
            "close": close,
            "EMA_50": 110.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=entry_price, current_pnl_pct=-4.0)
        assert ex.should_exit is True
        assert ex.urgency == 80
        assert ex.partial_pct == 1.0

    def test_no_exit_normal(self) -> None:
        """Normal conditions with no exit triggers → no exit."""
        ind_5m = {
            "RSI_14": 50.0,
            "close": 95.0,
            "EMA_50": 100.0,
        }
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=96.0, current_pnl_pct=-1.0)
        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_exit_signal_type(self) -> None:
        ind_5m = {"RSI_14": 70.0, "close": 115.0, "EMA_50": 110.0}
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=100.0, current_pnl_pct=5.0)
        assert isinstance(ex, ExitSignal)

    def test_no_exit_rsi_high_but_below_ema50(self) -> None:
        """RSI > 65 but close still below EMA_50 → no exit."""
        ind_5m = {"RSI_14": 70.0, "close": 95.0, "EMA_50": 100.0}
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=90.0, current_pnl_pct=5.5)
        assert ex.should_exit is False

    def test_no_exit_close_above_ema50_but_rsi_low(self) -> None:
        """close > EMA_50 but RSI <= 65 → no exit."""
        ind_5m = {"RSI_14": 60.0, "close": 115.0, "EMA_50": 110.0}
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=100.0, current_pnl_pct=5.0)
        assert ex.should_exit is False

    def test_divergence_resolved_priority_over_stop_loss(self) -> None:
        """When both conditions met, divergence resolved check comes first."""
        # RSI > 65 and close > EMA_50 AND close < entry * 0.97 simultaneously is
        # unlikely but let's ensure order is predictable (divergence resolved first).
        entry_price = 120.0
        close = 115.0  # < entry * 0.97 = 116.4
        ind_5m = {"RSI_14": 70.0, "close": close, "EMA_50": 110.0}
        ms = _make_market_state(indicators_5m=ind_5m)
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=entry_price, current_pnl_pct=-4.2)
        assert ex.should_exit is True
        assert ex.urgency == 50  # divergence resolved takes priority

    def test_no_exit_when_empty_indicators(self) -> None:
        """Missing indicators should not crash and should produce no exit."""
        ms = _make_market_state(indicators_5m={})
        ex = self.strat.generate_exit_signal(_PAIR, ms, entry_price=100.0, current_pnl_pct=0.0)
        assert ex.should_exit is False
