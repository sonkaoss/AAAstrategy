"""MarketStructureStrategy — sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_TRANSITION_UP,
    SynthesizedRegime.REGIME_ACCUMULATION,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
]

_TF = "5m"
_BUY_THRESHOLD = 55


class MarketStructureStrategy(BaseStrategy):
    """Market structure strategy based on BOS/CHoCH patterns and order blocks."""

    def __init__(self) -> None:
        super().__init__(name="MarketStructure", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:  # noqa: PLR0912
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)  # noqa: E731

        close = g("close")
        ema9 = g("EMA_9")
        ema21 = g("EMA_21")
        ema50 = g("EMA_50")
        ema200 = g("EMA_200")
        bb_upper = g("BB_upper_20")
        bb_lower = g("BB_lower_20")
        rsi = g("RSI_14")
        adx = g("ADX_14")  # noqa: F841 — fetched for indicators_used list
        roc = g("ROC_9")  # noqa: F841 — fetched for indicators_used list
        volume_sma = g("Volume_SMA_20")  # noqa: F841 — fetched for indicators_used list
        atr = g("ATR_14")

        if close <= 0:
            return self._no_signal(pair)

        score = 0
        reasons: list[str] = []

        # Break of Structure (BOS) bullish: close > EMA_50
        if ema50 > 0 and close > ema50:
            score += 20
            reasons.append("BOS bullish: close > EMA_50 (+20)")

        # Change of Character (CHoCH): EMA_9 > EMA_21
        if ema9 > ema21:
            score += 15
            reasons.append("CHoCH: EMA_9 > EMA_21 (+15)")

        # Higher high: close > BB_upper_20 * 0.99
        if bb_upper > 0 and close > bb_upper * 0.99:
            score += 10
            reasons.append("Higher high: close > BB_upper_20 * 0.99 (+10)")

        # Higher low: BB_lower_20 > EMA_200 (lower boundary rising)
        if ema200 > 0 and bb_lower > ema200:
            score += 10
            reasons.append("Higher low: BB_lower_20 > EMA_200 (+10)")

        # Order Block support: close near EMA_200 (within 2%) and RSI < 40
        if ema200 > 0 and abs(close - ema200) / ema200 <= 0.02 and rsi < 40:
            score += 15
            reasons.append("Order Block support: close near EMA_200 and RSI < 40 (+15)")

        # RSI crossing 50: RSI > 50 and RSI < 65
        if 50 < rsi < 65:
            score += 10
            reasons.append(f"RSI crossing 50: RSI={rsi:.1f} in (50, 65) (+10)")

        # BTC context bonus
        if market_state.btc_trend == "bullish":
            score += 5
            reasons.append("BTC trend bullish (+5)")

        if score < _BUY_THRESHOLD:
            return self._no_signal(pair)

        confidence = min(score, 90)

        # Stop loss: max(EMA_200, close - ATR * 3.0) — use higher (tighter)
        sl_ema200 = ema200 if ema200 > 0 else 0.0
        sl_atr = close - atr * 3.0
        stop_loss = max(sl_ema200, sl_atr)

        # Take-profit levels
        take_profit_levels = [
            {"price": round(ema50 + atr, 8), "pct": 0.25},
            {"price": round(bb_upper, 8), "pct": 0.25},
            {"price": round(close + atr * 3, 8), "pct": 0.25},
            {"price": round(close + atr * 5, 8), "pct": 0.25},
        ]

        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="BUY",
            confidence=confidence,
            entry_price=close,
            stop_loss=round(stop_loss, 8),
            take_profit_levels=take_profit_levels,
            indicators_used=[
                "close", "EMA_9", "EMA_21", "EMA_50", "EMA_200",
                "BB_upper_20", "BB_lower_20", "RSI_14", "ADX_14",
                "ROC_9", "Volume_SMA_20", "ATR_14",
            ],
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
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)  # noqa: E731

        close = g("close")
        ema9 = g("EMA_9")
        ema21 = g("EMA_21")
        ema50 = g("EMA_50")

        # Structure broken: close < EMA_50 → urgency 70, full exit
        if ema50 > 0 and close < ema50:
            return ExitSignal(
                should_exit=True,
                urgency=70,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Structure broken: close < EMA_50",
                timestamp=datetime.now(timezone.utc),
            )

        # Momentum shift: EMA_9 < EMA_21 → urgency 50, partial 0.5
        if ema9 < ema21:
            return ExitSignal(
                should_exit=True,
                urgency=50,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Momentum shift: EMA_9 < EMA_21",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
