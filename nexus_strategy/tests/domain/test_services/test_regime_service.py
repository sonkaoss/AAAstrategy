"""Tests for RegimeService — 3-layer regime detection with synthesizer."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
)
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.services.regime_service import RegimeService


# ---------------------------------------------------------------------------
# Fixture: mock config provider
# ---------------------------------------------------------------------------

@pytest.fixture()
def config() -> MagicMock:
    mock = MagicMock(spec=IConfigProvider)
    mock.get.return_value = 3  # regime.transition_min_candles default
    return mock


@pytest.fixture()
def service(config: MagicMock) -> RegimeService:
    return RegimeService(config)


# ===================================================================
# Micro regime tests
# ===================================================================

class TestDetectMicro:
    def test_detect_micro_trending_up(self, service: RegimeService) -> None:
        """EMAs aligned up + ADX>25 + RSI 55-65 + ROC positive -> MICRO_TRENDING_UP."""
        ind_5m = {
            "EMA_9": 105.0,
            "EMA_21": 103.0,
            "EMA_50": 100.0,
            "ADX_14": 30.0,
            "RSI_14": 60.0,
            "ROC_9": 1.5,
            "CMF_20": 0.1,
            "BB_width_20": 0.04,
            "BB_upper_20": 110.0,
            "BB_lower_20": 95.0,
            "close": 104.0,
            "ATR_14": 1.0,
            "Volume_SMA_20": 1.0,
            "OBV": 1000.0,
        }
        ind_15m = {"RSI_14": 58.0, "ADX_14": 28.0}
        result = service.detect_micro(ind_5m, ind_15m)
        assert result == MicroRegime.MICRO_TRENDING_UP

    def test_detect_micro_trending_down(self, service: RegimeService) -> None:
        """EMAs aligned down + ADX>25 + ROC negative -> MICRO_TRENDING_DOWN."""
        ind_5m = {
            "EMA_9": 95.0,
            "EMA_21": 98.0,
            "EMA_50": 100.0,
            "ADX_14": 30.0,
            "RSI_14": 40.0,
            "ROC_9": -1.5,
            "CMF_20": -0.1,
            "BB_width_20": 0.04,
            "BB_upper_20": 110.0,
            "BB_lower_20": 90.0,
            "close": 96.0,
            "ATR_14": 1.0,
            "Volume_SMA_20": 1.0,
            "OBV": 1000.0,
        }
        ind_15m = {"RSI_14": 42.0, "ADX_14": 28.0}
        result = service.detect_micro(ind_5m, ind_15m)
        assert result == MicroRegime.MICRO_TRENDING_DOWN

    def test_detect_micro_ranging(self, service: RegimeService) -> None:
        """ADX<20 + BB_width<0.03 + small ROC -> MICRO_RANGING."""
        ind_5m = {
            "EMA_9": 100.0,
            "EMA_21": 100.5,
            "EMA_50": 100.2,
            "ADX_14": 15.0,
            "RSI_14": 50.0,
            "ROC_9": 0.2,
            "CMF_20": 0.0,
            "BB_width_20": 0.025,
            "BB_upper_20": 102.0,
            "BB_lower_20": 98.0,
            "close": 100.0,
            "ATR_14": 0.5,
            "Volume_SMA_20": 1.0,
            "OBV": 1000.0,
        }
        ind_15m = {"RSI_14": 50.0, "ADX_14": 14.0}
        result = service.detect_micro(ind_5m, ind_15m)
        assert result == MicroRegime.MICRO_RANGING

    def test_detect_micro_squeeze(self, service: RegimeService) -> None:
        """BB_width<0.02 + ADX<15 -> MICRO_SQUEEZE."""
        # Use RSI outside 40-60 range and ROC >= 0.5 to suppress RANGING/CHOPPY
        ind_5m = {
            "EMA_9": 100.0,
            "EMA_21": 100.0,
            "EMA_50": 100.0,
            "ADX_14": 12.0,
            "RSI_14": 38.0,
            "ROC_9": 0.6,
            "CMF_20": 0.0,
            "BB_width_20": 0.015,
            "BB_upper_20": 101.0,
            "BB_lower_20": 99.0,
            "close": 100.0,
            "ATR_14": 0.3,
            "Volume_SMA_20": 1.0,
            "OBV": 1000.0,
        }
        ind_15m = {"RSI_14": 38.0, "ADX_14": 12.0}
        result = service.detect_micro(ind_5m, ind_15m)
        assert result == MicroRegime.MICRO_SQUEEZE

    def test_detect_micro_breakout_up(self, service: RegimeService) -> None:
        """close > BB_upper + ROC > 1.0 -> MICRO_BREAKOUT_UP."""
        ind_5m = {
            "EMA_9": 106.0,
            "EMA_21": 104.0,
            "EMA_50": 102.0,
            "ADX_14": 25.0,
            "RSI_14": 72.0,
            "ROC_9": 2.5,
            "CMF_20": 0.2,
            "BB_width_20": 0.04,
            "BB_upper_20": 105.0,
            "BB_lower_20": 95.0,
            "close": 107.0,
            "ATR_14": 1.5,
            "Volume_SMA_20": 1.5,
            "OBV": 2000.0,
        }
        ind_15m = {"RSI_14": 65.0, "ADX_14": 22.0}
        result = service.detect_micro(ind_5m, ind_15m)
        assert result == MicroRegime.MICRO_BREAKOUT_UP

    def test_detect_micro_empty_indicators(self, service: RegimeService) -> None:
        """Empty indicators should not crash, returns some valid MicroRegime."""
        result = service.detect_micro({}, {})
        assert isinstance(result, MicroRegime)


# ===================================================================
# Mid regime tests
# ===================================================================

class TestDetectMid:
    def test_detect_mid_trend_bull_strong(self, service: RegimeService) -> None:
        """Aligned EMAs up, high ADX, positive MACD -> TREND_BULL_STRONG."""
        ind_1h = {
            "EMA_12": 110.0,
            "EMA_26": 108.0,
            "EMA_50": 105.0,
            "EMA_200": 100.0,
            "ADX_14": 35.0,
            "RSI_14": 62.0,
            "MACD_12_26_9": 2.0,
            "MACDh_12_26_9": 0.5,
            "BB_width_20": 0.04,
            "BB_upper_20": 115.0,
            "BB_lower_20": 95.0,
            "close": 110.0,
            "CMF_20": 0.15,
        }
        ind_4h = {"ADX_14": 32.0, "RSI_14": 60.0}
        result = service.detect_mid(ind_1h, ind_4h)
        assert result == MidRegime.TREND_BULL_STRONG

    def test_detect_mid_trend_bear_strong(self, service: RegimeService) -> None:
        """Aligned EMAs down, high ADX, negative MACD -> TREND_BEAR_STRONG."""
        ind_1h = {
            "EMA_12": 90.0,
            "EMA_26": 93.0,
            "EMA_50": 96.0,
            "EMA_200": 100.0,
            "ADX_14": 35.0,
            "RSI_14": 35.0,
            "MACD_12_26_9": -2.0,
            "MACDh_12_26_9": -0.5,
            "BB_width_20": 0.04,
            "BB_upper_20": 105.0,
            "BB_lower_20": 85.0,
            "close": 90.0,
            "CMF_20": -0.15,
        }
        ind_4h = {"ADX_14": 32.0, "RSI_14": 37.0}
        result = service.detect_mid(ind_1h, ind_4h)
        assert result == MidRegime.TREND_BEAR_STRONG

    def test_detect_mid_ranging_tight(self, service: RegimeService) -> None:
        """Low ADX, narrow BB -> RANGING_TIGHT."""
        ind_1h = {
            "EMA_12": 100.0,
            "EMA_26": 100.5,
            "EMA_50": 100.2,
            "EMA_200": 100.0,
            "ADX_14": 14.0,
            "RSI_14": 50.0,
            "MACD_12_26_9": 0.0,
            "MACDh_12_26_9": 0.0,
            "BB_width_20": 0.02,
            "BB_upper_20": 101.0,
            "BB_lower_20": 99.0,
            "close": 100.0,
            "CMF_20": 0.0,
        }
        ind_4h = {"ADX_14": 13.0, "RSI_14": 50.0}
        result = service.detect_mid(ind_1h, ind_4h)
        assert result == MidRegime.RANGING_TIGHT

    def test_detect_mid_accumulation(self, service: RegimeService) -> None:
        """Low RSI recovering, positive CMF -> ACCUMULATION."""
        ind_1h = {
            "EMA_12": 97.0,
            "EMA_26": 98.0,
            "EMA_50": 99.0,
            "EMA_200": 100.0,
            "ADX_14": 18.0,
            "RSI_14": 33.0,
            "MACD_12_26_9": -0.5,
            "MACDh_12_26_9": 0.1,  # turning positive
            "BB_width_20": 0.04,
            "BB_upper_20": 103.0,
            "BB_lower_20": 95.0,
            "close": 96.0,
            "CMF_20": 0.05,
        }
        ind_4h = {"ADX_14": 16.0, "RSI_14": 34.0}
        result = service.detect_mid(ind_1h, ind_4h)
        assert result == MidRegime.ACCUMULATION


# ===================================================================
# Macro regime tests
# ===================================================================

class TestDetectMacro:
    def test_detect_macro_bull_healthy(self, service: RegimeService) -> None:
        """close > EMA_200, moderate RSI, normal sentinel -> MACRO_BULL_HEALTHY."""
        ind_1d = {
            "EMA_200": 100.0,
            "RSI_14": 60.0,
            "close": 110.0,
            "MACD_12_26_9": 1.0,
            "MACDh_12_26_9": 0.2,
            "ADX_14": 28.0,
        }
        sentinel = {"risk_score": 40, "funding_rate": 0.01, "fear_greed": 55}
        result = service.detect_macro(ind_1d, sentinel)
        assert result == MacroRegime.MACRO_BULL_HEALTHY

    def test_detect_macro_bear_panic(self, service: RegimeService) -> None:
        """close < EMA_200, very low RSI, high fear -> MACRO_BEAR_PANIC."""
        ind_1d = {
            "EMA_200": 100.0,
            "RSI_14": 22.0,
            "close": 80.0,
            "MACD_12_26_9": -3.0,
            "MACDh_12_26_9": -1.0,
            "ADX_14": 40.0,
        }
        sentinel = {"risk_score": 90, "funding_rate": -0.05, "fear_greed": 15}
        result = service.detect_macro(ind_1d, sentinel)
        assert result == MacroRegime.MACRO_BEAR_PANIC

    def test_detect_macro_uncertain(self, service: RegimeService) -> None:
        """Conflicting signals -> MACRO_UNCERTAIN."""
        ind_1d = {
            "EMA_200": 100.0,
            "RSI_14": 50.0,
            "close": 100.0,
            "MACD_12_26_9": 0.0,
            "MACDh_12_26_9": 0.0,
            "ADX_14": 15.0,
        }
        sentinel = {"risk_score": 50, "fear_greed": 50}
        result = service.detect_macro(ind_1d, sentinel)
        assert result == MacroRegime.MACRO_UNCERTAIN

    def test_detect_macro_no_sentinel(self, service: RegimeService) -> None:
        """Empty sentinel_data should still produce a valid result."""
        ind_1d = {
            "EMA_200": 100.0,
            "RSI_14": 55.0,
            "close": 108.0,
            "MACD_12_26_9": 0.5,
            "MACDh_12_26_9": 0.1,
            "ADX_14": 22.0,
        }
        result = service.detect_macro(ind_1d, {})
        assert isinstance(result, MacroRegime)


# ===================================================================
# Synthesizer tests
# ===================================================================

class TestSynthesize:
    def test_synthesize_all_bullish(self, service: RegimeService) -> None:
        """3 bullish layers -> STRONG_BULL, confidence >= 85."""
        synth, confidence, strategies = service.synthesize(
            MicroRegime.MICRO_TRENDING_UP,
            MidRegime.TREND_BULL_STRONG,
            MacroRegime.MACRO_BULL_HEALTHY,
        )
        assert synth == SynthesizedRegime.REGIME_STRONG_BULL
        assert confidence >= 85

    def test_synthesize_all_bearish(self, service: RegimeService) -> None:
        """3 bearish layers -> STRONG_BEAR."""
        synth, confidence, strategies = service.synthesize(
            MicroRegime.MICRO_TRENDING_DOWN,
            MidRegime.TREND_BEAR_STRONG,
            MacroRegime.MACRO_BEAR_GRIND,
        )
        assert synth == SynthesizedRegime.REGIME_STRONG_BEAR
        assert confidence >= 85

    def test_synthesize_mixed(self, service: RegimeService) -> None:
        """Conflicting signals -> lower confidence."""
        synth, confidence, strategies = service.synthesize(
            MicroRegime.MICRO_TRENDING_UP,
            MidRegime.TREND_BEAR_STRONG,
            MacroRegime.MACRO_UNCERTAIN,
        )
        assert confidence < 70

    def test_synthesize_returns_strategies(self, service: RegimeService) -> None:
        """Strategies list should not be empty, except for PANIC."""
        synth, confidence, strategies = service.synthesize(
            MicroRegime.MICRO_TRENDING_UP,
            MidRegime.TREND_BULL_STRONG,
            MacroRegime.MACRO_BULL_HEALTHY,
        )
        assert len(strategies) > 0

    def test_synthesize_panic_empty_strategies(self, service: RegimeService) -> None:
        """PANIC regime should return empty strategies."""
        synth, confidence, strategies = service.synthesize(
            MicroRegime.MICRO_BREAKOUT_DOWN,
            MidRegime.TREND_BEAR_STRONG,
            MacroRegime.MACRO_BEAR_PANIC,
        )
        assert synth == SynthesizedRegime.REGIME_PANIC
        assert strategies == []


# ===================================================================
# Integration tests — detect_full
# ===================================================================

class TestDetectFull:
    def _make_all_indicators(
        self,
        micro_bull: bool = False,
        micro_bear: bool = False,
        mid_bull: bool = False,
        mid_bear: bool = False,
        macro_bull: bool = False,
        macro_bear: bool = False,
    ) -> dict[str, dict[str, float]]:
        """Helper to build indicator dicts for various regime combinations."""
        ind_5m: dict[str, float] = {
            "EMA_9": 105.0 if micro_bull else (95.0 if micro_bear else 100.0),
            "EMA_21": 103.0 if micro_bull else (98.0 if micro_bear else 100.5),
            "EMA_50": 100.0,
            "ADX_14": 30.0 if (micro_bull or micro_bear) else 15.0,
            "RSI_14": 60.0 if micro_bull else (40.0 if micro_bear else 50.0),
            "ROC_9": 1.5 if micro_bull else (-1.5 if micro_bear else 0.1),
            "CMF_20": 0.1 if micro_bull else (-0.1 if micro_bear else 0.0),
            "BB_width_20": 0.04,
            "BB_upper_20": 110.0,
            "BB_lower_20": 90.0,
            "close": 104.0 if micro_bull else (96.0 if micro_bear else 100.0),
            "ATR_14": 1.0,
            "Volume_SMA_20": 1.0,
            "OBV": 1000.0,
        }
        ind_15m: dict[str, float] = {
            "RSI_14": 58.0 if micro_bull else (42.0 if micro_bear else 50.0),
            "ADX_14": 28.0 if (micro_bull or micro_bear) else 14.0,
        }
        ind_1h: dict[str, float] = {
            "EMA_12": 110.0 if mid_bull else (90.0 if mid_bear else 100.0),
            "EMA_26": 108.0 if mid_bull else (93.0 if mid_bear else 100.5),
            "EMA_50": 105.0 if mid_bull else (96.0 if mid_bear else 100.2),
            "EMA_200": 100.0,
            "ADX_14": 35.0 if (mid_bull or mid_bear) else 14.0,
            "RSI_14": 62.0 if mid_bull else (35.0 if mid_bear else 50.0),
            "MACD_12_26_9": 2.0 if mid_bull else (-2.0 if mid_bear else 0.0),
            "MACDh_12_26_9": 0.5 if mid_bull else (-0.5 if mid_bear else 0.0),
            "BB_width_20": 0.04,
            "BB_upper_20": 115.0,
            "BB_lower_20": 85.0,
            "close": 110.0 if mid_bull else (90.0 if mid_bear else 100.0),
            "CMF_20": 0.15 if mid_bull else (-0.15 if mid_bear else 0.0),
        }
        ind_4h: dict[str, float] = {
            "ADX_14": 32.0 if (mid_bull or mid_bear) else 13.0,
            "RSI_14": 60.0 if mid_bull else (37.0 if mid_bear else 50.0),
        }
        ind_1d: dict[str, float] = {
            "EMA_200": 100.0,
            "RSI_14": 60.0 if macro_bull else (25.0 if macro_bear else 50.0),
            "close": 110.0 if macro_bull else (80.0 if macro_bear else 100.0),
            "MACD_12_26_9": 1.0 if macro_bull else (-3.0 if macro_bear else 0.0),
            "MACDh_12_26_9": 0.2 if macro_bull else (-1.0 if macro_bear else 0.0),
            "ADX_14": 28.0 if (macro_bull or macro_bear) else 15.0,
        }
        return {
            "5m": ind_5m,
            "15m": ind_15m,
            "1h": ind_1h,
            "4h": ind_4h,
            "1d": ind_1d,
        }

    def test_detect_full_returns_composite_regime(self, service: RegimeService) -> None:
        """detect_full should return a valid CompositeRegime."""
        all_ind = self._make_all_indicators(
            micro_bull=True, mid_bull=True, macro_bull=True,
        )
        sentinel = {"risk_score": 40, "funding_rate": 0.01, "fear_greed": 55}
        result = service.detect_full(all_ind, sentinel)
        assert isinstance(result, CompositeRegime)
        assert isinstance(result.micro, MicroRegime)
        assert isinstance(result.mid, MidRegime)
        assert isinstance(result.macro, MacroRegime)
        assert isinstance(result.synthesized, SynthesizedRegime)
        assert 0 <= result.confidence <= 100
        assert result.risk_multiplier > 0
        assert result.max_position_size > 0
        assert result.timestamp is not None

    def test_detect_full_transition_smoothing(self, service: RegimeService, config: MagicMock) -> None:
        """Rapid regime changes should be smoothed (held for min_candles)."""
        config.get.return_value = 3  # need 3 candles before switching

        # First call: establishes initial regime (bullish)
        bull_ind = self._make_all_indicators(
            micro_bull=True, mid_bull=True, macro_bull=True,
        )
        sentinel = {"risk_score": 40, "fear_greed": 55}
        r1 = service.detect_full(bull_ind, sentinel)
        first_regime = r1.synthesized

        # Second call: switch to ranging (not panic, so smoothing applies)
        # Use neutral indicators that will not trigger PANIC
        neutral_ind = self._make_all_indicators()  # all neutral/ranging
        r2 = service.detect_full(neutral_ind, {"risk_score": 50, "fear_greed": 50})
        # Should still hold the previous regime because duration (1) < min_candles (3)
        assert r2.synthesized == first_regime

    def test_detect_full_panic_instant(self, service: RegimeService, config: MagicMock) -> None:
        """PANIC should bypass transition smoothing (instant switch)."""
        config.get.return_value = 3

        # First: establish a bullish regime
        bull_ind = self._make_all_indicators(
            micro_bull=True, mid_bull=True, macro_bull=True,
        )
        sentinel = {"risk_score": 40, "fear_greed": 55}
        r1 = service.detect_full(bull_ind, sentinel)

        # Second: panic conditions — should switch immediately
        panic_ind = self._make_all_indicators(
            micro_bear=True, mid_bear=True, macro_bear=True,
        )
        # Set extreme panic indicators on the daily
        panic_ind["1d"]["RSI_14"] = 22.0
        panic_ind["1d"]["close"] = 80.0
        panic_sentinel = {"risk_score": 95, "fear_greed": 10, "funding_rate": -0.05}
        r2 = service.detect_full(panic_ind, panic_sentinel)
        assert r2.synthesized == SynthesizedRegime.REGIME_PANIC
