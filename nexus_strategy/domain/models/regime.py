"""Regime domain models — immutable data structures for market regime classification."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING


class MicroRegime(Enum):
    """Short-term (micro) market regime classification."""

    MICRO_TRENDING_UP = "micro_trending_up"
    MICRO_TRENDING_DOWN = "micro_trending_down"
    MICRO_RANGING = "micro_ranging"
    MICRO_VOLATILE = "micro_volatile"
    MICRO_SQUEEZE = "micro_squeeze"
    MICRO_BREAKOUT_UP = "micro_breakout_up"
    MICRO_BREAKOUT_DOWN = "micro_breakout_down"
    MICRO_CHOPPY = "micro_choppy"


class MidRegime(Enum):
    """Medium-term market regime classification."""

    TREND_BULL_STRONG = "trend_bull_strong"
    TREND_BULL_WEAK = "trend_bull_weak"
    TREND_BEAR_STRONG = "trend_bear_strong"
    TREND_BEAR_WEAK = "trend_bear_weak"
    RANGING_TIGHT = "ranging_tight"
    RANGING_WIDE = "ranging_wide"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    REVERSAL_BULLISH = "reversal_bullish"
    REVERSAL_BEARISH = "reversal_bearish"


class MacroRegime(Enum):
    """Long-term (macro) market regime classification."""

    MACRO_BULL_EUPHORIA = "macro_bull_euphoria"
    MACRO_BULL_HEALTHY = "macro_bull_healthy"
    MACRO_BULL_EARLY = "macro_bull_early"
    MACRO_BEAR_PANIC = "macro_bear_panic"
    MACRO_BEAR_GRIND = "macro_bear_grind"
    MACRO_BEAR_EARLY = "macro_bear_early"
    MACRO_TRANSITION_UP = "macro_transition_up"
    MACRO_TRANSITION_DOWN = "macro_transition_down"
    MACRO_UNCERTAIN = "macro_uncertain"


class SynthesizedRegime(Enum):
    """Synthesized overall market regime combining micro, mid and macro signals."""

    REGIME_STRONG_BULL = "strong_bull"
    REGIME_MODERATE_BULL = "moderate_bull"
    REGIME_WEAK_BULL = "weak_bull"
    REGIME_STRONG_BEAR = "strong_bear"
    REGIME_MODERATE_BEAR = "moderate_bear"
    REGIME_WEAK_BEAR = "weak_bear"
    REGIME_RANGING_TIGHT = "ranging_tight"
    REGIME_RANGING_WIDE = "ranging_wide"
    REGIME_SQUEEZE = "squeeze"
    REGIME_BREAKOUT_BULL = "breakout_bull"
    REGIME_BREAKOUT_BEAR = "breakout_bear"
    REGIME_ACCUMULATION = "accumulation"
    REGIME_DISTRIBUTION = "distribution"
    REGIME_TRANSITION_UP = "transition_up"
    REGIME_TRANSITION_DOWN = "transition_down"
    REGIME_EUPHORIA = "euphoria"
    REGIME_PANIC = "panic"
    REGIME_CHOPPY = "choppy"
    REGIME_UNCERTAIN = "uncertain"


_BULLISH_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_STRONG_BULL,
    SynthesizedRegime.REGIME_MODERATE_BULL,
    SynthesizedRegime.REGIME_WEAK_BULL,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
    SynthesizedRegime.REGIME_ACCUMULATION,
    SynthesizedRegime.REGIME_TRANSITION_UP,
    SynthesizedRegime.REGIME_EUPHORIA,
})

_BEARISH_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_STRONG_BEAR,
    SynthesizedRegime.REGIME_MODERATE_BEAR,
    SynthesizedRegime.REGIME_WEAK_BEAR,
    SynthesizedRegime.REGIME_BREAKOUT_BEAR,
    SynthesizedRegime.REGIME_DISTRIBUTION,
    SynthesizedRegime.REGIME_TRANSITION_DOWN,
    SynthesizedRegime.REGIME_PANIC,
})


@dataclass(frozen=True)
class CompositeRegime:
    """Composite regime combining all timeframe analyses into a single actionable regime."""

    micro: MicroRegime
    mid: MidRegime
    macro: MacroRegime
    synthesized: SynthesizedRegime
    confidence: int  # 0-100
    duration_candles: int
    transition_probability: float
    recommended_strategies: list[str]
    risk_multiplier: float
    max_position_size: float
    timestamp: datetime

    @property
    def is_bullish(self) -> bool:
        """Return True when the synthesized regime is bullish."""
        return self.synthesized in _BULLISH_REGIMES

    @property
    def is_bearish(self) -> bool:
        """Return True when the synthesized regime is bearish."""
        return self.synthesized in _BEARISH_REGIMES

    @property
    def is_neutral(self) -> bool:
        """Return True when the synthesized regime is neither bullish nor bearish."""
        return not self.is_bullish and not self.is_bearish

    @property
    def is_high_confidence(self) -> bool:
        """Return True when confidence is >= 70."""
        return self.confidence >= 70
