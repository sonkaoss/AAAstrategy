"""Tests for regime domain models."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
    _BULLISH_REGIMES,
    _BEARISH_REGIMES,
)


class TestMicroRegime:
    def test_has_eight_values(self):
        assert len(MicroRegime) == 8

    def test_specific_values(self):
        assert MicroRegime.MICRO_TRENDING_UP.value == "micro_trending_up"
        assert MicroRegime.MICRO_TRENDING_DOWN.value == "micro_trending_down"
        assert MicroRegime.MICRO_RANGING.value == "micro_ranging"
        assert MicroRegime.MICRO_VOLATILE.value == "micro_volatile"
        assert MicroRegime.MICRO_SQUEEZE.value == "micro_squeeze"
        assert MicroRegime.MICRO_BREAKOUT_UP.value == "micro_breakout_up"
        assert MicroRegime.MICRO_BREAKOUT_DOWN.value == "micro_breakout_down"
        assert MicroRegime.MICRO_CHOPPY.value == "micro_choppy"

    def test_all_values_prefixed_micro(self):
        for member in MicroRegime:
            assert member.value.startswith("micro_"), f"{member.name} value does not start with 'micro_'"


class TestMidRegime:
    def test_has_ten_values(self):
        assert len(MidRegime) == 10

    def test_specific_values(self):
        assert MidRegime.TREND_BULL_STRONG.value == "trend_bull_strong"
        assert MidRegime.TREND_BULL_WEAK.value == "trend_bull_weak"
        assert MidRegime.TREND_BEAR_STRONG.value == "trend_bear_strong"
        assert MidRegime.TREND_BEAR_WEAK.value == "trend_bear_weak"
        assert MidRegime.RANGING_TIGHT.value == "ranging_tight"
        assert MidRegime.RANGING_WIDE.value == "ranging_wide"
        assert MidRegime.ACCUMULATION.value == "accumulation"
        assert MidRegime.DISTRIBUTION.value == "distribution"
        assert MidRegime.REVERSAL_BULLISH.value == "reversal_bullish"
        assert MidRegime.REVERSAL_BEARISH.value == "reversal_bearish"


class TestMacroRegime:
    def test_has_nine_values(self):
        assert len(MacroRegime) == 9

    def test_specific_values(self):
        assert MacroRegime.MACRO_BULL_EUPHORIA.value == "macro_bull_euphoria"
        assert MacroRegime.MACRO_BULL_HEALTHY.value == "macro_bull_healthy"
        assert MacroRegime.MACRO_BULL_EARLY.value == "macro_bull_early"
        assert MacroRegime.MACRO_BEAR_PANIC.value == "macro_bear_panic"
        assert MacroRegime.MACRO_BEAR_GRIND.value == "macro_bear_grind"
        assert MacroRegime.MACRO_BEAR_EARLY.value == "macro_bear_early"
        assert MacroRegime.MACRO_TRANSITION_UP.value == "macro_transition_up"
        assert MacroRegime.MACRO_TRANSITION_DOWN.value == "macro_transition_down"
        assert MacroRegime.MACRO_UNCERTAIN.value == "macro_uncertain"

    def test_all_values_prefixed_macro(self):
        for member in MacroRegime:
            assert member.value.startswith("macro_"), f"{member.name} value does not start with 'macro_'"


class TestSynthesizedRegime:
    def test_has_nineteen_values(self):
        assert len(SynthesizedRegime) == 19

    def test_specific_values(self):
        assert SynthesizedRegime.REGIME_STRONG_BULL.value == "strong_bull"
        assert SynthesizedRegime.REGIME_MODERATE_BULL.value == "moderate_bull"
        assert SynthesizedRegime.REGIME_WEAK_BULL.value == "weak_bull"
        assert SynthesizedRegime.REGIME_STRONG_BEAR.value == "strong_bear"
        assert SynthesizedRegime.REGIME_MODERATE_BEAR.value == "moderate_bear"
        assert SynthesizedRegime.REGIME_WEAK_BEAR.value == "weak_bear"
        assert SynthesizedRegime.REGIME_RANGING_TIGHT.value == "ranging_tight"
        assert SynthesizedRegime.REGIME_RANGING_WIDE.value == "ranging_wide"
        assert SynthesizedRegime.REGIME_SQUEEZE.value == "squeeze"
        assert SynthesizedRegime.REGIME_BREAKOUT_BULL.value == "breakout_bull"
        assert SynthesizedRegime.REGIME_BREAKOUT_BEAR.value == "breakout_bear"
        assert SynthesizedRegime.REGIME_ACCUMULATION.value == "accumulation"
        assert SynthesizedRegime.REGIME_DISTRIBUTION.value == "distribution"
        assert SynthesizedRegime.REGIME_TRANSITION_UP.value == "transition_up"
        assert SynthesizedRegime.REGIME_TRANSITION_DOWN.value == "transition_down"
        assert SynthesizedRegime.REGIME_EUPHORIA.value == "euphoria"
        assert SynthesizedRegime.REGIME_PANIC.value == "panic"
        assert SynthesizedRegime.REGIME_CHOPPY.value == "choppy"
        assert SynthesizedRegime.REGIME_UNCERTAIN.value == "uncertain"

    def test_values_have_no_regime_prefix(self):
        for member in SynthesizedRegime:
            assert not member.value.startswith("regime_"), (
                f"{member.name} value should not start with 'regime_'"
            )


class TestBullishBearishFrozensets:
    def test_bullish_regimes_contains_expected(self):
        expected = {
            SynthesizedRegime.REGIME_STRONG_BULL,
            SynthesizedRegime.REGIME_MODERATE_BULL,
            SynthesizedRegime.REGIME_WEAK_BULL,
            SynthesizedRegime.REGIME_BREAKOUT_BULL,
            SynthesizedRegime.REGIME_ACCUMULATION,
            SynthesizedRegime.REGIME_TRANSITION_UP,
            SynthesizedRegime.REGIME_EUPHORIA,
        }
        assert _BULLISH_REGIMES == expected

    def test_bearish_regimes_contains_expected(self):
        expected = {
            SynthesizedRegime.REGIME_STRONG_BEAR,
            SynthesizedRegime.REGIME_MODERATE_BEAR,
            SynthesizedRegime.REGIME_WEAK_BEAR,
            SynthesizedRegime.REGIME_BREAKOUT_BEAR,
            SynthesizedRegime.REGIME_DISTRIBUTION,
            SynthesizedRegime.REGIME_TRANSITION_DOWN,
            SynthesizedRegime.REGIME_PANIC,
        }
        assert _BEARISH_REGIMES == expected

    def test_frozensets_are_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            _BULLISH_REGIMES.add(SynthesizedRegime.REGIME_UNCERTAIN)  # type: ignore
        with pytest.raises((AttributeError, TypeError)):
            _BEARISH_REGIMES.add(SynthesizedRegime.REGIME_UNCERTAIN)  # type: ignore


class TestCompositeRegime:
    def _make_composite(self, synthesized=SynthesizedRegime.REGIME_STRONG_BULL, confidence=80):
        return CompositeRegime(
            micro=MicroRegime.MICRO_TRENDING_UP,
            mid=MidRegime.TREND_BULL_STRONG,
            macro=MacroRegime.MACRO_BULL_HEALTHY,
            synthesized=synthesized,
            confidence=confidence,
            duration_candles=10,
            transition_probability=0.2,
            recommended_strategies=["momentum"],
            risk_multiplier=1.0,
            max_position_size=0.05,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def test_is_frozen(self):
        regime = self._make_composite()
        with pytest.raises((AttributeError, TypeError)):
            regime.confidence = 50  # type: ignore

    def test_is_bullish_true(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_STRONG_BULL)
        assert regime.is_bullish is True

    def test_is_bullish_false_for_bear(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_STRONG_BEAR)
        assert regime.is_bullish is False

    def test_is_bearish_true(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_STRONG_BEAR)
        assert regime.is_bearish is True

    def test_is_bearish_false_for_bull(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_STRONG_BULL)
        assert regime.is_bearish is False

    def test_is_neutral_true(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_UNCERTAIN)
        assert regime.is_neutral is True

    def test_is_neutral_false_for_bull(self):
        regime = self._make_composite(SynthesizedRegime.REGIME_STRONG_BULL)
        assert regime.is_neutral is False

    def test_is_high_confidence_at_70(self):
        regime = self._make_composite(confidence=70)
        assert regime.is_high_confidence is True

    def test_is_high_confidence_above_70(self):
        regime = self._make_composite(confidence=90)
        assert regime.is_high_confidence is True

    def test_is_high_confidence_below_70(self):
        regime = self._make_composite(confidence=69)
        assert regime.is_high_confidence is False

    def test_all_bullish_regimes_trigger_is_bullish(self):
        for sr in _BULLISH_REGIMES:
            regime = self._make_composite(synthesized=sr)
            assert regime.is_bullish is True, f"{sr} should be bullish"

    def test_all_bearish_regimes_trigger_is_bearish(self):
        for sr in _BEARISH_REGIMES:
            regime = self._make_composite(synthesized=sr)
            assert regime.is_bearish is True, f"{sr} should be bearish"
