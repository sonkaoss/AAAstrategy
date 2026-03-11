"""VolumeProfile sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_MODERATE_BULL,
    SynthesizedRegime.REGIME_ACCUMULATION,
    SynthesizedRegime.REGIME_RANGING_WIDE,
]

_TF = "5m"
_BUY_THRESHOLD = 50


class VolumeProfileStrategy(BaseStrategy):
    """Volume-profile strategy targeting institutional accumulation and money-flow signals."""

    def __init__(self) -> None:
        super().__init__(name="VolumeProfile", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a BUY signal when institutional accumulation conditions are met."""
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)  # noqa: E731

        close = g("close")
        obv = g("OBV")
        cmf = g("CMF_20")
        volume_sma = g("Volume_SMA_20")
        rsi = g("RSI_14")
        ema_21 = g("EMA_21")
        ema_50 = g("EMA_50")
        bb_lower = g("BB_lower_20")
        bb_upper = g("BB_upper_20")
        mfi = g("MFI_14")
        atr = g("ATR_14")

        score = 0
        reasons: list[str] = []

        # CMF accumulation
        if cmf > 0.1:
            score += 15
            reasons.append(f"CMF={cmf:.3f} > 0.1 (+15)")
        elif cmf > 0.05:
            score += 10
            reasons.append(f"CMF={cmf:.3f} > 0.05 (+10)")
        elif cmf > 0:
            score += 5
            reasons.append(f"CMF={cmf:.3f} > 0 (+5)")

        # MFI oversold with CMF positive
        if mfi < 30 and cmf > 0:
            score += 15
            reasons.append(f"MFI={mfi:.1f} < 30 and CMF > 0 (+15)")

        # Close below BB lower with positive CMF — reversal with institutional support
        if bb_lower > 0 and close < bb_lower and cmf > 0:
            score += 20
            reasons.append(f"close={close:.4f} < BB_lower={bb_lower:.4f} and CMF > 0 (+20)")

        # Close near EMA_21 from above with RSI 40-55 — pullback entry
        if ema_21 > 0 and close >= ema_21 and 40 <= rsi <= 55:
            score += 15
            reasons.append(f"close near EMA_21={ema_21:.4f} from above, RSI={rsi:.1f} in [40, 55] (+15)")

        # Volume above average — flag as active
        if volume_sma > 0:
            score += 5
            reasons.append(f"Volume_SMA_20={volume_sma:.0f} > 0 (+5)")

        # RSI not overbought
        if rsi < 65:
            score += 5
            reasons.append(f"RSI={rsi:.1f} < 65 (+5)")

        if score < _BUY_THRESHOLD:
            return self._no_signal(pair)

        confidence = min(score, 90)

        stop_loss = close - atr * 2.5

        take_profit_levels = [
            {"price": ema_50, "pct": 0.25},
            {"price": bb_upper, "pct": 0.25},
            {"price": close * 1.03, "pct": 0.25},
            {"price": close * 1.05, "pct": 0.25},
        ]

        indicators_used = [
            "close", "OBV", "CMF_20", "Volume_SMA_20", "RSI_14",
            "EMA_21", "EMA_50", "BB_lower_20", "BB_upper_20", "MFI_14", "ATR_14",
        ]

        reasoning = (
            f"VolumeProfile BUY: score={score}, CMF={cmf:.3f}, MFI={mfi:.1f}, "
            f"close={close:.4f}, BB_lower={bb_lower:.4f}, RSI={rsi:.1f}; "
            + "; ".join(reasons)
        )

        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="BUY",
            confidence=confidence,
            entry_price=close,
            stop_loss=stop_loss,
            take_profit_levels=take_profit_levels,
            indicators_used=indicators_used,
            reasoning=reasoning,
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
        """Generate an exit signal when money-flow or overbought conditions are met."""
        g = lambda key, default=0.0: self._get(market_state, pair, _TF, key, default)  # noqa: E731

        cmf = g("CMF_20")
        close = g("close")
        bb_upper = g("BB_upper_20")
        mfi = g("MFI_14")

        # Overbought with volume — full exit (check before CMF to give proper priority)
        if bb_upper > 0 and close > bb_upper and mfi > 80:
            return ExitSignal(
                should_exit=True,
                urgency=70,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Overbought with volume",
                timestamp=datetime.now(timezone.utc),
            )

        # Money flow turning negative — partial exit
        if cmf < -0.1:
            return ExitSignal(
                should_exit=True,
                urgency=60,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Money flow negative",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
