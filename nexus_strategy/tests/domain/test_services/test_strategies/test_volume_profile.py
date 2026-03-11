"""Tests for VolumeProfileStrategy."""
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
from nexus_strategy.domain.services.strategies.volume_profile import VolumeProfileStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAIR = "ETH/USDT"


def _make_regime(
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_ACCUMULATION,
) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_RANGING,
        mid=MidRegime.ACCUMULATION,
        macro=MacroRegime.MACRO_UNCERTAIN,
        synthesized=synthesized,
        confidence=65,
        duration_candles=10,
        transition_probability=0.1,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )


def _make_market_state(
    pair: str = _PAIR,
    indicators_5m: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_ACCUMULATION,
) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = _make_regime(synthesized)
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
        btc_change_1h=0.1,
        btc_change_24h=0.5,
        btc_above_ema200=True,
        btc_trend="neutral",
        market_phase="ACCUMULATION",
        altcoin_season_index=50,
        fear_greed=40,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _accumulation_indicators(
    close: float = 100.0,
    obv: float = 5000.0,
    cmf: float = 0.15,
    volume_sma: float = 1000.0,
    rsi: float = 45.0,
    ema_21: float = 102.0,
    ema_50: float = 105.0,
    bb_lower: float = 98.0,
    bb_upper: float = 115.0,
    mfi: float = 28.0,
    atr: float = 1.5,
) -> dict:
    return {
        "close": close,
        "OBV": obv,
        "CMF_20": cmf,
        "Volume_SMA_20": volume_sma,
        "RSI_14": rsi,
        "EMA_21": ema_21,
        "EMA_50": ema_50,
        "BB_lower_20": bb_lower,
        "BB_upper_20": bb_upper,
        "MFI_14": mfi,
        "ATR_14": atr,
    }


# ---------------------------------------------------------------------------
# Strategy setup tests
# ---------------------------------------------------------------------------


class TestVolumeProfileStrategySetup:
    def test_name_and_optimal_regimes(self) -> None:
        strat = VolumeProfileStrategy()
        assert strat.name == "VolumeProfile"
        regimes = strat.optimal_regimes
        assert SynthesizedRegime.REGIME_MODERATE_BULL in regimes
        assert SynthesizedRegime.REGIME_ACCUMULATION in regimes
        assert SynthesizedRegime.REGIME_RANGING_WIDE in regimes

    def test_regime_active_accumulation(self) -> None:
        strat = VolumeProfileStrategy()
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_ACCUMULATION) is True
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_MODERATE_BULL) is True
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_WIDE) is True
        # Not active for others
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BEAR) is False
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_RANGING_TIGHT) is False


# ---------------------------------------------------------------------------
# generate_signal — BUY conditions
# ---------------------------------------------------------------------------


class TestGenerateSignalBuy:
    def setup_method(self) -> None:
        self.strat = VolumeProfileStrategy()

    def test_institutional_accumulation_buy(self) -> None:
        """High CMF, low MFI, close near BB_lower → BUY signal."""
        ind = _accumulation_indicators(
            close=97.5,      # close < bb_lower=98 → +20 (with CMF>0)
            cmf=0.15,        # +15 (CMF > 0.1)
            mfi=28.0,        # +15 (MFI < 30 and CMF > 0)
            volume_sma=500.0,  # +5
            rsi=50.0,        # +5 (RSI < 65)
            bb_lower=98.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert sig.is_buy is True

    def test_no_accumulation_no_signal(self) -> None:
        """CMF negative, RSI high → NO_SIGNAL."""
        ind = _accumulation_indicators(
            cmf=-0.05,   # 0 pts
            mfi=70.0,    # 0 pts (MFI not < 30)
            rsi=70.0,    # 0 pts (RSI >= 65)
            close=110.0, # close > bb_lower → no reversal bonus
            volume_sma=0.0,  # 0 pts
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "NO_SIGNAL"
        assert sig.is_buy is False

    def test_pullback_entry(self) -> None:
        """Close near EMA_21 from above with moderate RSI → BUY if enough score."""
        ind = _accumulation_indicators(
            close=102.5,     # close >= ema_21=102, RSI in [40, 55] → +15
            ema_21=102.0,
            rsi=48.0,        # in [40, 55] → pullback bonus, also RSI < 65 → +5
            cmf=0.12,        # +15 (CMF > 0.1)
            mfi=35.0,        # MFI not < 30 → no +15
            volume_sma=300.0,  # +5
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        # score = 15 (CMF) + 15 (pullback) + 5 (volume) + 5 (RSI < 65) = 40
        # Need score >= 50; add more indicators to get there or verify threshold
        # With score=40, no signal is expected; adjust to reach threshold
        # Re-check: CMF=0.12 > 0.1 → +15; pullback close>=ema_21 and 40<=rsi<=55 → +15;
        # volume_sma=300 > 0 → +5; rsi=48 < 65 → +5; total = 40 < 50 → NO_SIGNAL
        assert sig.action == "NO_SIGNAL"

    def test_pullback_entry_with_mfi(self) -> None:
        """Close near EMA_21 + CMF positive + MFI oversold → BUY."""
        ind = _accumulation_indicators(
            close=102.5,     # close >= ema_21=102, RSI in [40, 55] → +15
            ema_21=102.0,
            rsi=48.0,        # RSI < 65 → +5; in [40, 55] → pullback +15
            cmf=0.12,        # +15
            mfi=25.0,        # MFI < 30 and CMF > 0 → +15
            volume_sma=300.0,  # +5
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        # score = 15 (CMF) + 15 (MFI oversold) + 15 (pullback) + 5 (volume) + 5 (RSI) = 55
        assert sig.action == "BUY"

    def test_confidence_capped_at_90(self) -> None:
        """Maximum possible score must be capped at 90."""
        ind = _accumulation_indicators(
            close=97.5,      # < bb_lower=98 → +20 (reversal with CMF>0)
            cmf=0.15,        # +15 (CMF > 0.1)
            mfi=25.0,        # +15 (MFI < 30 and CMF > 0)
            volume_sma=500.0,  # +5
            rsi=50.0,        # +5 (RSI < 65); in [40, 55] but close < ema_21 → no pullback
            ema_21=102.0,    # close < ema_21 → no pullback bonus
            bb_lower=98.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert sig.confidence <= 90

    def test_stop_loss_calculation(self) -> None:
        """Stop loss should be close - ATR * 2.5."""
        # Use a clearly accumulating scenario
        ind2 = _accumulation_indicators(
            close=97.5,
            atr=2.0,
            cmf=0.15,
            mfi=25.0,
            volume_sma=500.0,
            rsi=50.0,
            bb_lower=98.0,
        )
        ms = _make_market_state(indicators_5m=ind2)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        expected_sl = 97.5 - 2.0 * 2.5
        assert abs(sig.stop_loss - expected_sl) < 1e-9

    def test_take_profit_levels(self) -> None:
        """Take profit should have 4 levels with correct prices and pcts."""
        ind = _accumulation_indicators(
            close=97.5,
            ema_50=105.0,
            bb_upper=115.0,
            cmf=0.15,
            mfi=25.0,
            volume_sma=500.0,
            rsi=50.0,
            bb_lower=98.0,
        )
        ms = _make_market_state(indicators_5m=ind)
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "BUY"
        assert len(sig.take_profit_levels) == 4
        prices = [tp["price"] for tp in sig.take_profit_levels]
        pcts = [tp["pct"] for tp in sig.take_profit_levels]
        assert prices[0] == 105.0        # EMA_50
        assert prices[1] == 115.0        # BB_upper
        assert abs(prices[2] - 97.5 * 1.03) < 1e-9  # close * 1.03
        assert abs(prices[3] - 97.5 * 1.05) < 1e-9  # close * 1.05
        assert all(p == 0.25 for p in pcts)
        assert abs(sum(pcts) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# generate_exit_signal
# ---------------------------------------------------------------------------


class TestGenerateExitSignal:
    def setup_method(self) -> None:
        self.strat = VolumeProfileStrategy()

    def test_exit_cmf_negative(self) -> None:
        """CMF < -0.1 → urgency 60, partial 0.5, reason 'Money flow negative'."""
        ind = {"CMF_20": -0.15, "close": 100.0, "BB_upper_20": 110.0, "MFI_14": 50.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 95.0, 1.0)
        assert ex.should_exit is True
        assert ex.urgency == 60
        assert ex.partial_pct == 0.5
        assert ex.reason == "Money flow negative"

    def test_exit_overbought_volume(self) -> None:
        """Close > BB_upper and MFI > 80 → urgency 70, full exit."""
        ind = {"CMF_20": 0.05, "close": 116.0, "BB_upper_20": 115.0, "MFI_14": 85.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 100.0, 5.0)
        assert ex.should_exit is True
        assert ex.urgency == 70
        assert ex.partial_pct == 1.0
        assert ex.reason == "Overbought with volume"

    def test_no_exit_normal(self) -> None:
        """Normal conditions → no exit."""
        ind = {"CMF_20": 0.05, "close": 105.0, "BB_upper_20": 115.0, "MFI_14": 50.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 100.0, 2.0)
        assert ex.should_exit is False
        assert ex.urgency == 0

    def test_no_exit_cmf_slightly_negative(self) -> None:
        """CMF between -0.1 and 0 → no exit triggered."""
        ind = {"CMF_20": -0.05, "close": 100.0, "BB_upper_20": 110.0, "MFI_14": 50.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 95.0, 1.0)
        assert ex.should_exit is False

    def test_no_exit_overbought_without_volume(self) -> None:
        """Close > BB_upper but MFI <= 80 → no exit."""
        ind = {"CMF_20": 0.05, "close": 116.0, "BB_upper_20": 115.0, "MFI_14": 75.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 100.0, 5.0)
        assert ex.should_exit is False

    def test_missing_indicators_no_crash(self) -> None:
        """Missing indicators should not cause a crash — return no exit or signal."""
        ms = _make_market_state(indicators_5m={})
        # generate_signal — should return NO_SIGNAL
        sig = self.strat.generate_signal(_PAIR, ms)
        assert sig.action == "NO_SIGNAL"
        # generate_exit_signal — should return no exit
        ex = self.strat.generate_exit_signal(_PAIR, ms, 100.0, 0.0)
        assert ex.should_exit is False

    def test_exit_signal_is_exit_signal_type(self) -> None:
        ind = {"CMF_20": -0.15, "close": 100.0, "BB_upper_20": 110.0, "MFI_14": 50.0}
        ms = _make_market_state(indicators_5m=ind)
        ex = self.strat.generate_exit_signal(_PAIR, ms, 95.0, 1.0)
        assert isinstance(ex, ExitSignal)
