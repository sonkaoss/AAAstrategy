"""MomentumBreakout sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_SQUEEZE,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
    SynthesizedRegime.REGIME_TRANSITION_UP,
    SynthesizedRegime.REGIME_ACCUMULATION,
]

_TF = "5m"
_BUY_THRESHOLD = 55


class MomentumBreakoutStrategy(BaseStrategy):
    """Momentum breakout strategy targeting squeeze-to-breakout transitions."""

    def __init__(self) -> None:
        super().__init__(name="MomentumBreakout", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:  # noqa: PLR0912
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)  # noqa: E731

        close = g("close")
        bb_upper = g("BB_upper_20")
        bb_lower = g("BB_lower_20")
        bb_width = g("BB_width_20")
        bb_mid = g("BB_mid_20")
        keltner_upper = g("Keltner_upper")
        keltner_lower = g("Keltner_lower")
        roc = g("ROC_9")
        adx = g("ADX_14")
        rsi = g("RSI_14")
        volume_sma = g("Volume_SMA_20")
        atr = g("ATR_14")
        obv = g("OBV")

        # Attempt to read current volume — None means indicator absent
        volume_raw = market_state.get_indicator(pair, _TF, "volume")

        if close <= 0:
            return self._no_signal(pair)

        score = 0
        reasons: list[str] = []

        # BB breakout: close > BB_upper
        if bb_upper > 0 and close > bb_upper:
            score += 25
            reasons.append("BB breakout (close > BB_upper_20)")

        # Strong ROC
        if roc > 1.5:
            score += 20
            reasons.append(f"ROC_9={roc:.2f} > 1.5 (+20)")
        elif roc > 1.0:
            score += 15
            reasons.append(f"ROC_9={roc:.2f} > 1.0 (+15)")
        elif roc > 0.5:
            score += 10
            reasons.append(f"ROC_9={roc:.2f} > 0.5 (+10)")

        # Volume explosion:
        #   - If the raw "volume" indicator is present, compare against SMA tiers.
        #   - Otherwise fall back to confirming that Volume_SMA_20 > 0 (volume data available).
        if volume_raw is not None and volume_sma > 0:
            if volume_raw > volume_sma * 2.0:
                score += 15
                reasons.append("Volume explosion (volume > 2x SMA, +15)")
            elif volume_raw > volume_sma * 1.5:
                score += 10
                reasons.append("Volume surge (volume > 1.5x SMA, +10)")
        elif volume_sma > 0:
            score += 15
            reasons.append("Volume_SMA_20 available (+15)")

        # ADX > 25
        if adx > 25:
            score += 10
            reasons.append(f"ADX_14={adx:.1f} > 25")

        # RSI 55-75
        if 55 <= rsi <= 75:
            score += 10
            reasons.append(f"RSI_14={rsi:.1f} in [55, 75]")

        # OBV positive trend
        if obv > 0:
            score += 5
            reasons.append(f"OBV={obv:.0f} > 0 (positive trend)")

        # Keltner squeeze release: simplified — recent squeeze if BB_width < 0.03
        if 0 < bb_width < 0.03:
            score += 20
            reasons.append(f"Keltner squeeze release (BB_width={bb_width:.4f} < 0.03, +20)")

        # Fake breakout filter: RSI > 80 reduces score by 20
        if rsi > 80:
            score -= 20
            reasons.append(f"Fake breakout filter: RSI_14={rsi:.1f} > 80 (-20)")

        if score < _BUY_THRESHOLD:
            return self._no_signal(pair)

        confidence = min(score, 95)

        # Stop loss: higher of BB_mid_20 or close - ATR*2.0
        sl_bb_mid = bb_mid if bb_mid > 0 else 0.0
        sl_atr = close - atr * 2.0
        stop_loss = max(sl_bb_mid, sl_atr)

        # Take-profit levels
        take_profit_levels = [
            {"price": round(close + atr * 1.5, 8), "pct": 0.3},
            {"price": round(close + atr * 3.0, 8), "pct": 0.3},
            {"price": round(close + atr * 5.0, 8), "pct": 0.4},
        ]

        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="BUY",
            confidence=confidence,
            entry_price=close,
            stop_loss=stop_loss,
            take_profit_levels=take_profit_levels,
            indicators_used=[
                "close", "BB_upper_20", "BB_lower_20", "BB_width_20", "BB_mid_20",
                "Keltner_upper", "Keltner_lower", "ROC_9", "ADX_14", "RSI_14",
                "Volume_SMA_20", "ATR_14", "OBV",
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
        bb_upper = g("BB_upper_20")
        roc = g("ROC_9")

        # Failed breakout: price fell back below BB_upper after entry was above it
        if bb_upper > 0 and close < bb_upper and entry_price > bb_upper:
            return ExitSignal(
                should_exit=True,
                urgency=80,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Price fell back below BB_upper_20 — breakout failed",
                timestamp=datetime.now(timezone.utc),
            )

        # Momentum turning negative
        if roc < 0:
            return ExitSignal(
                should_exit=True,
                urgency=60,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason=f"ROC_9={roc:.2f} < 0 — momentum reversed",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
