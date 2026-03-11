"""TrendFollowingStrategy — sub-strategy for trending bull markets."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES = [
    SynthesizedRegime.REGIME_STRONG_BULL,
    SynthesizedRegime.REGIME_MODERATE_BULL,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
]

_TF = "5m"


class TrendFollowingStrategy(BaseStrategy):
    """Trend-following strategy that scores momentum confluence and enters on pullbacks."""

    def __init__(self) -> None:
        super().__init__(name="TrendFollowing", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:  # noqa: D102
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)

        ema9 = g("EMA_9")
        ema21 = g("EMA_21")
        ema50 = g("EMA_50")
        ema200 = g("EMA_200")
        adx = g("ADX_14")
        macd = g("MACD_12_26_9")
        macd_hist = g("MACD_hist")
        rsi = g("RSI_14")
        supertrend = g("Supertrend_10_3")
        close = g("close")
        atr = g("ATR_14")

        # Volume_SMA_20 — use None sentinel to detect missing value
        volume_sma_raw = market_state.get_indicator(pair, _TF, "Volume_SMA_20")

        score = 0
        reasons: list[str] = []

        # EMA alignment
        if ema9 > ema21 > ema50 > ema200:
            score += 20
            reasons.append("Full EMA alignment (9>21>50>200)")
        elif ema9 > ema21 > ema50:
            score += 15
            reasons.append("3-EMA alignment (9>21>50)")
        elif ema9 > ema21:
            score += 10
            reasons.append("Short EMA alignment (9>21)")

        # ADX strength
        if adx > 30:
            score += 20
            reasons.append(f"ADX {adx:.1f} > 30 (strong trend)")
        elif adx > 25:
            score += 15
            reasons.append(f"ADX {adx:.1f} > 25")
        elif adx > 20:
            score += 10
            reasons.append(f"ADX {adx:.1f} > 20")

        # MACD positive + histogram positive
        if macd > 0 and macd_hist > 0:
            score += 15
            reasons.append("MACD positive with positive histogram")

        # RSI sweet spot
        if 50 <= rsi <= 70:
            score += 15
            reasons.append(f"RSI {rsi:.1f} in optimal zone (50-70)")
        elif 45 <= rsi <= 75:
            score += 10
            reasons.append(f"RSI {rsi:.1f} in acceptable zone (45-75)")

        # EMA pullback: close within 1% of EMA_21 and above it
        if ema21 > 0:
            diff_pct = abs(close - ema21) / ema21
            if diff_pct <= 0.01 and close > ema21:
                score += 15
                reasons.append("EMA_21 pullback entry (close within 1% above EMA_21)")

        # Supertrend bullish
        if supertrend > 0 and close > supertrend:
            score += 10
            reasons.append("Supertrend bullish")

        # Volume above average (skip if indicator not present)
        if volume_sma_raw is not None and volume_sma_raw > 0:
            score += 5
            reasons.append("Volume above average")

        if score < 55:
            return self._no_signal(pair)

        confidence = min(score, 95)

        # Stop loss: max(EMA_50, close - ATR*3.0) — tighter (higher price)
        stop_loss = max(ema50, close - atr * 3.0)

        take_profit_levels = [
            {"price": round(close + atr * 2, 8), "pct": 0.25},
            {"price": round(close + atr * 3, 8), "pct": 0.25},
            {"price": round(close + atr * 4, 8), "pct": 0.25},
            {"price": round(close + atr * 6, 8), "pct": 0.25},
        ]

        indicators_used = [
            "EMA_9", "EMA_21", "EMA_50", "EMA_200",
            "ADX_14", "MACD_12_26_9", "MACD_hist",
            "RSI_14", "Supertrend_10_3", "close", "ATR_14", "Volume_SMA_20",
        ]

        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="BUY",
            confidence=confidence,
            entry_price=close,
            stop_loss=round(stop_loss, 8),
            take_profit_levels=take_profit_levels,
            indicators_used=indicators_used,
            reasoning="; ".join(reasons),
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Exit signal
    # ------------------------------------------------------------------

    def generate_exit_signal(
        self,
        pair: str,
        market_state: MarketState,
        entry_price: float,
        current_pnl_pct: float,
    ) -> ExitSignal:
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)

        ema9 = g("EMA_9")
        ema21 = g("EMA_21")
        ema50 = g("EMA_50")
        adx = g("ADX_14")
        macd = g("MACD_12_26_9")
        macd_hist = g("MACD_hist")
        close = g("close")

        # Priority: most urgent condition wins (ordered by urgency descending)

        # urgency 75 — price broke below trend anchor
        if close < ema50:
            return ExitSignal(
                should_exit=True,
                urgency=75,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Price below EMA50",
                timestamp=datetime.now(timezone.utc),
            )

        # urgency 60 — trend momentum dying
        if adx < 20:
            return ExitSignal(
                should_exit=True,
                urgency=60,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Trend strength dying",
                timestamp=datetime.now(timezone.utc),
            )

        # urgency 50 — short-term trend cross
        if ema9 < ema21:
            return ExitSignal(
                should_exit=True,
                urgency=50,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Short-term trend weakening",
                timestamp=datetime.now(timezone.utc),
            )

        # urgency 40 — MACD momentum fading
        if macd_hist < 0 and macd > 0:
            return ExitSignal(
                should_exit=True,
                urgency=40,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.25,
                reason="MACD momentum fading",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
