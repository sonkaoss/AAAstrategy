"""MeanReversion sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_RANGING_TIGHT,
    SynthesizedRegime.REGIME_RANGING_WIDE,
    SynthesizedRegime.REGIME_WEAK_BEAR,
    SynthesizedRegime.REGIME_ACCUMULATION,
]


class MeanReversionStrategy(BaseStrategy):
    """Mean-reversion strategy targeting oversold conditions within ranging markets."""

    def __init__(self) -> None:
        super().__init__(name="MeanReversion", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a BUY signal when the asset is oversold within its Bollinger range."""

        # --- Fetch 5m indicators ---
        rsi = self._get(market_state, pair, "5m", "RSI_14")
        bb_lower = self._get(market_state, pair, "5m", "BB_lower_20")
        bb_upper = self._get(market_state, pair, "5m", "BB_upper_20")
        bb_mid = self._get(market_state, pair, "5m", "BB_mid_20")
        close = self._get(market_state, pair, "5m", "close")
        ema_50 = self._get(market_state, pair, "5m", "EMA_50")
        ema_21 = self._get(market_state, pair, "5m", "EMA_21")  # noqa: F841
        mfi = self._get(market_state, pair, "5m", "MFI_14")
        stoch_rsi_k = self._get(market_state, pair, "5m", "StochRSI_K")
        volume_sma = self._get(market_state, pair, "5m", "Volume_SMA_20")
        volume = self._get(market_state, pair, "5m", "volume")
        cmf = self._get(market_state, pair, "5m", "CMF_20")
        _atr = self._get(market_state, pair, "5m", "ATR_14")  # noqa: F841 — fetched per spec

        # --- Fetch 15m confirmation ---
        rsi_15m = self._get(market_state, pair, "15m", "RSI_14")

        # --- Bail early when no meaningful price data is present ---
        if close <= 0.0:
            return self._no_signal(pair)

        # --- Score system ---
        score = 0
        scored_indicators: list[str] = []

        # RSI oversold
        if rsi < 30:
            score += 25
            scored_indicators.append("RSI_14")
        elif rsi < 35:
            score += 15
            scored_indicators.append("RSI_14")
        elif rsi < 40:
            score += 10
            scored_indicators.append("RSI_14")

        # Close near/below BB lower
        if bb_lower > 0 and close <= bb_lower:
            score += 25
            scored_indicators.append("BB_lower_20")
        elif bb_lower > 0 and close <= bb_lower * 1.005:
            score += 15
            scored_indicators.append("BB_lower_20")

        # MFI oversold
        if mfi < 25:
            score += 15
            scored_indicators.append("MFI_14")
        elif mfi < 35:
            score += 10
            scored_indicators.append("MFI_14")

        # StochRSI oversold
        if stoch_rsi_k < 20:
            score += 15
            scored_indicators.append("StochRSI_K")
        elif stoch_rsi_k < 30:
            score += 10
            scored_indicators.append("StochRSI_K")

        # Volume confirmation: current volume > 1.5x Volume_SMA_20
        if volume_sma > 0 and volume > volume_sma * 1.5:
            score += 10
            scored_indicators.append("Volume_SMA_20")

        # CMF positive
        if cmf > 0.1:
            score += 10
            scored_indicators.append("CMF_20")
        elif cmf > 0:
            score += 5
            scored_indicators.append("CMF_20")

        # 15m RSI confirmation
        if rsi_15m < 35:
            score += 10
            scored_indicators.append("RSI_14_15m")

        if score < 50:
            return self._no_signal(pair)

        # --- Build signal ---
        confidence = min(score, 95)

        stop_loss = min(bb_lower, close * 0.97) if bb_lower > 0 else close * 0.97

        take_profit_levels = [
            {"price": bb_mid, "pct": 0.25},
            {"price": ema_50, "pct": 0.25},
            {"price": bb_upper, "pct": 0.25},
            {"price": ema_50 * 1.02, "pct": 0.25},
        ]

        indicators_used = scored_indicators

        reasoning = (
            f"MeanReversion BUY: score={score}, RSI={rsi:.1f}, "
            f"close={close:.4f}, BB_lower={bb_lower:.4f}, "
            f"MFI={mfi:.1f}, StochRSI_K={stoch_rsi_k:.1f}, CMF={cmf:.3f}"
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
        """Generate an exit signal when mean-reversion conditions are exhausted."""

        rsi = self._get(market_state, pair, "5m", "RSI_14")
        close = self._get(market_state, pair, "5m", "close")
        bb_upper = self._get(market_state, pair, "5m", "BB_upper_20")

        # RSI overbought — partial exit
        if rsi > 75:
            return ExitSignal(
                should_exit=True,
                urgency=70,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="RSI overbought",
                timestamp=datetime.now(timezone.utc),
            )

        # Close above BB upper — full exit
        if bb_upper > 0 and close > bb_upper:
            return ExitSignal(
                should_exit=True,
                urgency=75,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Price above BB upper",
                timestamp=datetime.now(timezone.utc),
            )

        # Decent PnL with elevated RSI — partial exit
        if current_pnl_pct > 3.0 and rsi > 60:
            return ExitSignal(
                should_exit=True,
                urgency=50,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Profit target with RSI rising",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
