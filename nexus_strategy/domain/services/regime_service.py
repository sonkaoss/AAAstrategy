"""RegimeService — 3-layer market regime detection with cross-timeframe synthesis.

Detects micro (5m/15m), mid (1h/4h), and macro (1d + sentinel) regimes,
then synthesizes them into a single actionable regime with confidence,
strategy recommendations, and risk parameters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
)
from nexus_strategy.domain.ports.config_port import IConfigProvider


# ---------------------------------------------------------------------------
# Strategy recommendations per synthesized regime
# ---------------------------------------------------------------------------

REGIME_STRATEGIES: dict[SynthesizedRegime, list[str]] = {
    SynthesizedRegime.REGIME_STRONG_BULL: ["TrendFollowing", "MomentumBreakout", "MarketStructure"],
    SynthesizedRegime.REGIME_MODERATE_BULL: ["TrendFollowing", "VolumeProfile", "MomentumBreakout"],
    SynthesizedRegime.REGIME_WEAK_BULL: ["MeanReversion", "TrendFollowing", "Divergence"],
    SynthesizedRegime.REGIME_STRONG_BEAR: ["TrendFollowing", "MomentumBreakout", "MarketStructure"],
    SynthesizedRegime.REGIME_MODERATE_BEAR: ["TrendFollowing", "VolumeProfile"],
    SynthesizedRegime.REGIME_WEAK_BEAR: ["MeanReversion", "TrendFollowing", "Divergence"],
    SynthesizedRegime.REGIME_RANGING_TIGHT: ["MeanReversion", "VolatilitySqueeze"],
    SynthesizedRegime.REGIME_RANGING_WIDE: ["MeanReversion", "VolumeProfile"],
    SynthesizedRegime.REGIME_SQUEEZE: ["VolatilitySqueeze", "MomentumBreakout"],
    SynthesizedRegime.REGIME_BREAKOUT_BULL: ["MomentumBreakout", "TrendFollowing"],
    SynthesizedRegime.REGIME_BREAKOUT_BEAR: ["MomentumBreakout", "TrendFollowing"],
    SynthesizedRegime.REGIME_ACCUMULATION: ["MeanReversion", "VolumeProfile", "MarketStructure"],
    SynthesizedRegime.REGIME_DISTRIBUTION: ["MeanReversion", "VolumeProfile", "MarketStructure"],
    SynthesizedRegime.REGIME_TRANSITION_UP: ["TrendFollowing", "MomentumBreakout"],
    SynthesizedRegime.REGIME_TRANSITION_DOWN: ["TrendFollowing", "MomentumBreakout"],
    SynthesizedRegime.REGIME_EUPHORIA: ["MomentumBreakout", "Divergence"],
    SynthesizedRegime.REGIME_PANIC: [],
    SynthesizedRegime.REGIME_CHOPPY: ["MeanReversion"],
    SynthesizedRegime.REGIME_UNCERTAIN: ["MeanReversion"],
}

# ---------------------------------------------------------------------------
# Risk multiplier per synthesized regime
# ---------------------------------------------------------------------------

RISK_MULTIPLIERS: dict[SynthesizedRegime, float] = {
    SynthesizedRegime.REGIME_STRONG_BULL: 1.2,
    SynthesizedRegime.REGIME_MODERATE_BULL: 1.0,
    SynthesizedRegime.REGIME_WEAK_BULL: 0.8,
    SynthesizedRegime.REGIME_STRONG_BEAR: 0.3,
    SynthesizedRegime.REGIME_MODERATE_BEAR: 0.5,
    SynthesizedRegime.REGIME_WEAK_BEAR: 0.6,
    SynthesizedRegime.REGIME_RANGING_TIGHT: 0.7,
    SynthesizedRegime.REGIME_RANGING_WIDE: 0.6,
    SynthesizedRegime.REGIME_SQUEEZE: 0.6,
    SynthesizedRegime.REGIME_BREAKOUT_BULL: 0.9,
    SynthesizedRegime.REGIME_BREAKOUT_BEAR: 0.4,
    SynthesizedRegime.REGIME_ACCUMULATION: 0.7,
    SynthesizedRegime.REGIME_DISTRIBUTION: 0.5,
    SynthesizedRegime.REGIME_TRANSITION_UP: 0.6,
    SynthesizedRegime.REGIME_TRANSITION_DOWN: 0.5,
    SynthesizedRegime.REGIME_EUPHORIA: 0.4,
    SynthesizedRegime.REGIME_PANIC: 0.2,
    SynthesizedRegime.REGIME_CHOPPY: 0.5,
    SynthesizedRegime.REGIME_UNCERTAIN: 0.5,
}

# ---------------------------------------------------------------------------
# Helpers: classify individual-layer regimes as bullish / bearish / neutral
# ---------------------------------------------------------------------------

_MICRO_BULLISH = frozenset({
    MicroRegime.MICRO_TRENDING_UP,
    MicroRegime.MICRO_BREAKOUT_UP,
})
_MICRO_BEARISH = frozenset({
    MicroRegime.MICRO_TRENDING_DOWN,
    MicroRegime.MICRO_BREAKOUT_DOWN,
})

_MID_BULLISH = frozenset({
    MidRegime.TREND_BULL_STRONG,
    MidRegime.TREND_BULL_WEAK,
    MidRegime.REVERSAL_BULLISH,
    MidRegime.ACCUMULATION,
})
_MID_BEARISH = frozenset({
    MidRegime.TREND_BEAR_STRONG,
    MidRegime.TREND_BEAR_WEAK,
    MidRegime.REVERSAL_BEARISH,
    MidRegime.DISTRIBUTION,
})

_MACRO_BULLISH = frozenset({
    MacroRegime.MACRO_BULL_EUPHORIA,
    MacroRegime.MACRO_BULL_HEALTHY,
    MacroRegime.MACRO_BULL_EARLY,
    MacroRegime.MACRO_TRANSITION_UP,
})
_MACRO_BEARISH = frozenset({
    MacroRegime.MACRO_BEAR_PANIC,
    MacroRegime.MACRO_BEAR_GRIND,
    MacroRegime.MACRO_BEAR_EARLY,
    MacroRegime.MACRO_TRANSITION_DOWN,
})


class RegimeService:
    """Detects market regimes across 3 timeframe layers and synthesizes them."""

    def __init__(self, config: IConfigProvider) -> None:
        self._config = config
        self._previous_synthesized: SynthesizedRegime | None = None
        self._regime_duration: int = 0  # candles in current regime
        self._transition_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Layer 1: Micro regime (5m / 15m)
    # ------------------------------------------------------------------

    def detect_micro(
        self,
        ind_5m: dict[str, float],
        ind_15m: dict[str, float],
    ) -> MicroRegime:
        """Score each MicroRegime candidate and return the highest-scoring one."""
        scores: dict[MicroRegime, float] = {r: 0.0 for r in MicroRegime}

        # Extract indicators with safe defaults
        rsi = ind_5m.get("RSI_14", 50.0)
        adx = ind_5m.get("ADX_14", 20.0)
        ema9 = ind_5m.get("EMA_9", 0.0)
        ema21 = ind_5m.get("EMA_21", 0.0)
        ema50 = ind_5m.get("EMA_50", 0.0)
        bb_width = ind_5m.get("BB_width_20", 0.0)
        bb_upper = ind_5m.get("BB_upper_20", 0.0)
        bb_lower = ind_5m.get("BB_lower_20", 0.0)
        close = ind_5m.get("close", 0.0)
        roc = ind_5m.get("ROC_9", 0.0)
        cmf = ind_5m.get("CMF_20", 0.0)

        # 15m confirmation
        adx_15m = ind_15m.get("ADX_14", 20.0)

        # --- TRENDING_UP ---
        if ema9 > ema21 > ema50 and ema50 > 0:
            scores[MicroRegime.MICRO_TRENDING_UP] += 3
        if adx > 25:
            scores[MicroRegime.MICRO_TRENDING_UP] += 2
        if 50 < rsi < 70:
            scores[MicroRegime.MICRO_TRENDING_UP] += 1
        if roc > 0:
            scores[MicroRegime.MICRO_TRENDING_UP] += 1
        if cmf > 0:
            scores[MicroRegime.MICRO_TRENDING_UP] += 1
        if adx_15m > 25:
            scores[MicroRegime.MICRO_TRENDING_UP] += 1

        # --- TRENDING_DOWN ---
        if ema9 < ema21 < ema50 and ema50 > 0:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 3
        if adx > 25:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 2
        if 30 < rsi < 50:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 1
        if roc < 0:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 1
        if cmf < 0:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 1
        if adx_15m > 25:
            scores[MicroRegime.MICRO_TRENDING_DOWN] += 1

        # --- RANGING ---
        if adx < 20:
            scores[MicroRegime.MICRO_RANGING] += 3
        if bb_width < 0.03:
            scores[MicroRegime.MICRO_RANGING] += 2
        if abs(roc) < 0.5:
            scores[MicroRegime.MICRO_RANGING] += 1
        if 40 < rsi < 60:
            scores[MicroRegime.MICRO_RANGING] += 1

        # --- VOLATILE ---
        if bb_width > 0.06:
            scores[MicroRegime.MICRO_VOLATILE] += 3
        if adx > 30:
            scores[MicroRegime.MICRO_VOLATILE] += 1
        if abs(roc) > 2.0:
            scores[MicroRegime.MICRO_VOLATILE] += 2

        # --- SQUEEZE ---
        if bb_width < 0.02:
            scores[MicroRegime.MICRO_SQUEEZE] += 4
        if adx < 15:
            scores[MicroRegime.MICRO_SQUEEZE] += 2

        # --- BREAKOUT_UP ---
        if close > bb_upper and bb_upper > 0:
            scores[MicroRegime.MICRO_BREAKOUT_UP] += 3
        if roc > 1.0:
            scores[MicroRegime.MICRO_BREAKOUT_UP] += 2
        if rsi > 60:
            scores[MicroRegime.MICRO_BREAKOUT_UP] += 1

        # --- BREAKOUT_DOWN ---
        if close < bb_lower and bb_lower > 0:
            scores[MicroRegime.MICRO_BREAKOUT_DOWN] += 3
        if roc < -1.0:
            scores[MicroRegime.MICRO_BREAKOUT_DOWN] += 2
        if rsi < 40:
            scores[MicroRegime.MICRO_BREAKOUT_DOWN] += 1

        # --- CHOPPY ---
        if adx < 15:
            scores[MicroRegime.MICRO_CHOPPY] += 2
        if abs(roc) < 0.3:
            scores[MicroRegime.MICRO_CHOPPY] += 1
        if 40 < rsi < 60:
            scores[MicroRegime.MICRO_CHOPPY] += 1

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Layer 2: Mid regime (1h / 4h)
    # ------------------------------------------------------------------

    def detect_mid(
        self,
        ind_1h: dict[str, float],
        ind_4h: dict[str, float],
    ) -> MidRegime:
        """Score each MidRegime candidate and return the highest-scoring one."""
        scores: dict[MidRegime, float] = {r: 0.0 for r in MidRegime}

        # 1h indicators
        ema12 = ind_1h.get("EMA_12", 0.0)
        ema26 = ind_1h.get("EMA_26", 0.0)
        ema50 = ind_1h.get("EMA_50", 0.0)
        ema200 = ind_1h.get("EMA_200", 0.0)
        adx = ind_1h.get("ADX_14", 20.0)
        rsi = ind_1h.get("RSI_14", 50.0)
        macd = ind_1h.get("MACD_12_26_9", 0.0)
        macd_hist = ind_1h.get("MACDh_12_26_9", 0.0)
        bb_width = ind_1h.get("BB_width_20", 0.0)
        bb_upper = ind_1h.get("BB_upper_20", 0.0)
        bb_lower = ind_1h.get("BB_lower_20", 0.0)
        close = ind_1h.get("close", 0.0)
        cmf = ind_1h.get("CMF_20", 0.0)

        # 4h confirmation
        adx_4h = ind_4h.get("ADX_14", 20.0)
        rsi_4h = ind_4h.get("RSI_14", 50.0)

        # --- TREND_BULL_STRONG ---
        if ema12 > ema26 > ema50 > ema200 and ema200 > 0:
            scores[MidRegime.TREND_BULL_STRONG] += 4
        if adx > 30:
            scores[MidRegime.TREND_BULL_STRONG] += 2
        if macd > 0:
            scores[MidRegime.TREND_BULL_STRONG] += 1
        if 55 < rsi < 75:
            scores[MidRegime.TREND_BULL_STRONG] += 1
        if adx_4h > 25:
            scores[MidRegime.TREND_BULL_STRONG] += 1

        # --- TREND_BULL_WEAK ---
        # Partial alignment: at least EMA_12 > EMA_26
        if ema12 > ema26 and not (ema12 > ema26 > ema50 > ema200 and ema200 > 0):
            scores[MidRegime.TREND_BULL_WEAK] += 2
        if 20 < adx < 30:
            scores[MidRegime.TREND_BULL_WEAK] += 2
        if macd > 0:
            scores[MidRegime.TREND_BULL_WEAK] += 1
        if 50 < rsi < 65:
            scores[MidRegime.TREND_BULL_WEAK] += 1

        # --- TREND_BEAR_STRONG ---
        if ema12 < ema26 < ema50 < ema200 and ema200 > 0:
            scores[MidRegime.TREND_BEAR_STRONG] += 4
        if adx > 30:
            scores[MidRegime.TREND_BEAR_STRONG] += 2
        if macd < 0:
            scores[MidRegime.TREND_BEAR_STRONG] += 1
        if 25 < rsi < 45:
            scores[MidRegime.TREND_BEAR_STRONG] += 1
        if adx_4h > 25:
            scores[MidRegime.TREND_BEAR_STRONG] += 1

        # --- TREND_BEAR_WEAK ---
        if ema12 < ema26 and not (ema12 < ema26 < ema50 < ema200 and ema200 > 0):
            scores[MidRegime.TREND_BEAR_WEAK] += 2
        if 20 < adx < 30:
            scores[MidRegime.TREND_BEAR_WEAK] += 2
        if macd < 0:
            scores[MidRegime.TREND_BEAR_WEAK] += 1
        if 35 < rsi < 50:
            scores[MidRegime.TREND_BEAR_WEAK] += 1

        # --- RANGING_TIGHT ---
        if adx < 20:
            scores[MidRegime.RANGING_TIGHT] += 3
        if bb_width < 0.03:
            scores[MidRegime.RANGING_TIGHT] += 3
        if 45 < rsi < 55:
            scores[MidRegime.RANGING_TIGHT] += 1
        if adx_4h < 20:
            scores[MidRegime.RANGING_TIGHT] += 1

        # --- RANGING_WIDE ---
        if adx < 20:
            scores[MidRegime.RANGING_WIDE] += 2
        if bb_width > 0.05:
            scores[MidRegime.RANGING_WIDE] += 3
        if 40 < rsi < 60:
            scores[MidRegime.RANGING_WIDE] += 1

        # --- ACCUMULATION ---
        if rsi < 35:
            scores[MidRegime.ACCUMULATION] += 3
        if close > 0 and bb_lower > 0 and close < bb_lower * 1.02:
            scores[MidRegime.ACCUMULATION] += 2
        if cmf > 0:
            scores[MidRegime.ACCUMULATION] += 2
        if macd_hist > 0:
            scores[MidRegime.ACCUMULATION] += 1

        # --- DISTRIBUTION ---
        if rsi > 65:
            scores[MidRegime.DISTRIBUTION] += 3
        if close > 0 and bb_upper > 0 and close > bb_upper * 0.98:
            scores[MidRegime.DISTRIBUTION] += 2
        if cmf < 0:
            scores[MidRegime.DISTRIBUTION] += 2
        if macd_hist < 0:
            scores[MidRegime.DISTRIBUTION] += 1

        # --- REVERSAL_BULLISH ---
        if rsi < 35:
            scores[MidRegime.REVERSAL_BULLISH] += 2
        if macd_hist > 0:
            scores[MidRegime.REVERSAL_BULLISH] += 2
        if close > 0 and bb_lower > 0 and close < bb_lower:
            scores[MidRegime.REVERSAL_BULLISH] += 2

        # --- REVERSAL_BEARISH ---
        if rsi > 65:
            scores[MidRegime.REVERSAL_BEARISH] += 2
        if macd_hist < 0:
            scores[MidRegime.REVERSAL_BEARISH] += 2
        if close > 0 and bb_upper > 0 and close > bb_upper:
            scores[MidRegime.REVERSAL_BEARISH] += 2

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Layer 3: Macro regime (1d + sentinel)
    # ------------------------------------------------------------------

    def detect_macro(
        self,
        ind_1d: dict[str, float],
        sentinel_data: dict[str, Any],
    ) -> MacroRegime:
        """Score each MacroRegime candidate and return the highest-scoring one."""
        scores: dict[MacroRegime, float] = {r: 0.0 for r in MacroRegime}

        ema200 = ind_1d.get("EMA_200", 0.0)
        rsi = ind_1d.get("RSI_14", 50.0)
        close = ind_1d.get("close", 0.0)
        adx = ind_1d.get("ADX_14", 20.0)

        # Sentinel data (all optional)
        funding_rate = sentinel_data.get("funding_rate", 0.0)
        fear_greed = sentinel_data.get("fear_greed", 50)
        risk_score = sentinel_data.get("risk_score", 50)

        # Price relative to EMA_200
        ema_ratio = close / ema200 if ema200 > 0 else 1.0

        # --- BULL_EUPHORIA ---
        if rsi > 70:
            scores[MacroRegime.MACRO_BULL_EUPHORIA] += 3
        if ema_ratio > 1.0:
            scores[MacroRegime.MACRO_BULL_EUPHORIA] += 1
        if funding_rate > 0.03:
            scores[MacroRegime.MACRO_BULL_EUPHORIA] += 2
        if fear_greed > 75:
            scores[MacroRegime.MACRO_BULL_EUPHORIA] += 2

        # --- BULL_HEALTHY ---
        if 50 < rsi < 70:
            scores[MacroRegime.MACRO_BULL_HEALTHY] += 3
        if ema_ratio > 1.0:
            scores[MacroRegime.MACRO_BULL_HEALTHY] += 2
        if 30 <= fear_greed <= 75:
            scores[MacroRegime.MACRO_BULL_HEALTHY] += 1
        if adx > 20:
            scores[MacroRegime.MACRO_BULL_HEALTHY] += 1

        # --- BULL_EARLY ---
        if ema_ratio > 1.0 and ema_ratio < 1.05:
            scores[MacroRegime.MACRO_BULL_EARLY] += 3
        if 45 < rsi < 60:
            scores[MacroRegime.MACRO_BULL_EARLY] += 2

        # --- BEAR_PANIC ---
        if rsi < 30:
            scores[MacroRegime.MACRO_BEAR_PANIC] += 3
        if ema_ratio < 1.0:
            scores[MacroRegime.MACRO_BEAR_PANIC] += 1
        if fear_greed < 25:
            scores[MacroRegime.MACRO_BEAR_PANIC] += 2
        if risk_score > 80:
            scores[MacroRegime.MACRO_BEAR_PANIC] += 2

        # --- BEAR_GRIND ---
        if 30 <= rsi <= 45:
            scores[MacroRegime.MACRO_BEAR_GRIND] += 3
        if ema_ratio < 1.0:
            scores[MacroRegime.MACRO_BEAR_GRIND] += 2
        if adx > 20:
            scores[MacroRegime.MACRO_BEAR_GRIND] += 1

        # --- BEAR_EARLY ---
        if ema_ratio < 1.0 and ema_ratio > 0.95:
            scores[MacroRegime.MACRO_BEAR_EARLY] += 3
        if 40 < rsi < 55:
            scores[MacroRegime.MACRO_BEAR_EARLY] += 2

        # --- TRANSITION_UP ---
        if 0.95 < ema_ratio < 1.0:
            scores[MacroRegime.MACRO_TRANSITION_UP] += 4
        if rsi > 45:
            scores[MacroRegime.MACRO_TRANSITION_UP] += 1

        # --- TRANSITION_DOWN ---
        if 1.0 < ema_ratio < 1.05:
            scores[MacroRegime.MACRO_TRANSITION_DOWN] += 3
        if rsi < 55:
            scores[MacroRegime.MACRO_TRANSITION_DOWN] += 1

        # --- UNCERTAIN ---
        if 45 <= rsi <= 55:
            scores[MacroRegime.MACRO_UNCERTAIN] += 2
        if 0.98 < ema_ratio < 1.02:
            scores[MacroRegime.MACRO_UNCERTAIN] += 2
        if adx < 20:
            scores[MacroRegime.MACRO_UNCERTAIN] += 2

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Synthesizer
    # ------------------------------------------------------------------

    def synthesize(
        self,
        micro: MicroRegime,
        mid: MidRegime,
        macro: MacroRegime,
    ) -> tuple[SynthesizedRegime, int, list[str]]:
        """Map 3-layer regimes to a single SynthesizedRegime with confidence and strategies."""

        micro_bull = micro in _MICRO_BULLISH
        micro_bear = micro in _MICRO_BEARISH
        mid_bull = mid in _MID_BULLISH
        mid_bear = mid in _MID_BEARISH
        macro_bull = macro in _MACRO_BULLISH
        macro_bear = macro in _MACRO_BEARISH

        bull_count = sum([micro_bull, mid_bull, macro_bull])
        bear_count = sum([micro_bear, mid_bear, macro_bear])

        # Special-case: panic
        if macro == MacroRegime.MACRO_BEAR_PANIC and bear_count >= 2:
            regime = SynthesizedRegime.REGIME_PANIC
            confidence = 90 + (5 if bear_count == 3 else 0)
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Special-case: euphoria
        if macro == MacroRegime.MACRO_BULL_EUPHORIA and bull_count >= 2:
            regime = SynthesizedRegime.REGIME_EUPHORIA
            confidence = 85 + (5 if bull_count == 3 else 0)
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # All 3 layers agree
        if bull_count == 3:
            regime = SynthesizedRegime.REGIME_STRONG_BULL
            confidence = 90
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if bear_count == 3:
            regime = SynthesizedRegime.REGIME_STRONG_BEAR
            confidence = 90
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # 2 of 3 agree
        if bull_count == 2:
            # Check mid-layer for strong vs moderate
            if mid in (MidRegime.TREND_BULL_STRONG,):
                regime = SynthesizedRegime.REGIME_MODERATE_BULL
                confidence = 75
            else:
                regime = SynthesizedRegime.REGIME_WEAK_BULL
                confidence = 65
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if bear_count == 2:
            if mid in (MidRegime.TREND_BEAR_STRONG,):
                regime = SynthesizedRegime.REGIME_MODERATE_BEAR
                confidence = 75
            else:
                regime = SynthesizedRegime.REGIME_WEAK_BEAR
                confidence = 65
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Specific micro-layer patterns
        if micro == MicroRegime.MICRO_SQUEEZE:
            regime = SynthesizedRegime.REGIME_SQUEEZE
            confidence = 60
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if micro == MicroRegime.MICRO_BREAKOUT_UP:
            regime = SynthesizedRegime.REGIME_BREAKOUT_BULL
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if micro == MicroRegime.MICRO_BREAKOUT_DOWN:
            regime = SynthesizedRegime.REGIME_BREAKOUT_BEAR
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Mid-layer-specific patterns
        if mid == MidRegime.ACCUMULATION:
            regime = SynthesizedRegime.REGIME_ACCUMULATION
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if mid == MidRegime.DISTRIBUTION:
            regime = SynthesizedRegime.REGIME_DISTRIBUTION
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if mid in (MidRegime.RANGING_TIGHT,):
            regime = SynthesizedRegime.REGIME_RANGING_TIGHT
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if mid in (MidRegime.RANGING_WIDE,):
            regime = SynthesizedRegime.REGIME_RANGING_WIDE
            confidence = 55
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Macro transition patterns
        if macro == MacroRegime.MACRO_TRANSITION_UP:
            regime = SynthesizedRegime.REGIME_TRANSITION_UP
            confidence = 50
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        if macro == MacroRegime.MACRO_TRANSITION_DOWN:
            regime = SynthesizedRegime.REGIME_TRANSITION_DOWN
            confidence = 50
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Micro choppy
        if micro == MicroRegime.MICRO_CHOPPY:
            regime = SynthesizedRegime.REGIME_CHOPPY
            confidence = 45
            return regime, confidence, REGIME_STRATEGIES.get(regime, [])

        # Fallback: mixed / conflicting signals
        regime = SynthesizedRegime.REGIME_UNCERTAIN
        confidence = 40
        return regime, confidence, REGIME_STRATEGIES.get(regime, [])

    # ------------------------------------------------------------------
    # Full detection pipeline
    # ------------------------------------------------------------------

    def detect_full(
        self,
        all_indicators: dict[str, dict[str, float]],
        sentinel_data: dict[str, Any],
    ) -> CompositeRegime:
        """Orchestrate 3-layer detection, synthesize, apply transition smoothing."""

        ind_5m = all_indicators.get("5m", {})
        ind_15m = all_indicators.get("15m", {})
        ind_1h = all_indicators.get("1h", {})
        ind_4h = all_indicators.get("4h", {})
        ind_1d = all_indicators.get("1d", {})

        micro = self.detect_micro(ind_5m, ind_15m)
        mid = self.detect_mid(ind_1h, ind_4h)
        macro = self.detect_macro(ind_1d, sentinel_data)
        synthesized, confidence, strategies = self.synthesize(micro, mid, macro)

        # Transition smoothing
        min_candles: int = self._config.get("regime.transition_min_candles", 3)
        if synthesized == SynthesizedRegime.REGIME_PANIC:
            min_candles = 0  # instant transition for panic

        if synthesized == self._previous_synthesized:
            self._regime_duration += 1
        else:
            if self._regime_duration < min_candles and self._previous_synthesized is not None:
                # Hold previous regime — not enough candles elapsed
                synthesized = self._previous_synthesized
                confidence = max(30, confidence - 20)
                strategies = REGIME_STRATEGIES.get(synthesized, [])
            else:
                self._transition_history.append({
                    "from": self._previous_synthesized,
                    "to": synthesized,
                    "duration": self._regime_duration,
                })
                self._regime_duration = 1
                self._previous_synthesized = synthesized

        risk_mult = RISK_MULTIPLIERS.get(synthesized, 0.5)

        return CompositeRegime(
            micro=micro,
            mid=mid,
            macro=macro,
            synthesized=synthesized,
            confidence=confidence,
            duration_candles=self._regime_duration,
            transition_probability=0.0,  # calculated later by learning engine
            recommended_strategies=strategies,
            risk_multiplier=risk_mult,
            max_position_size=min(1.0, risk_mult + 0.2),
            timestamp=datetime.now(timezone.utc),
        )
