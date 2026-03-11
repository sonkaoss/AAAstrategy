"""VolatilitySqueeze sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_SQUEEZE,
    SynthesizedRegime.REGIME_RANGING_TIGHT,
    SynthesizedRegime.REGIME_ACCUMULATION,
]


class VolatilitySqueezeStrategy(BaseStrategy):
    """Volatility squeeze strategy that enters on breakout from compressed price ranges."""

    def __init__(self) -> None:
        super().__init__(name="VolatilitySqueeze", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a BUY signal when a squeeze is detected with bullish directional bias."""

        # --- Fetch 5m indicators ---
        bb_upper = self._get(market_state, pair, "5m", "BB_upper_20")
        bb_lower = self._get(market_state, pair, "5m", "BB_lower_20")
        bb_width = self._get(market_state, pair, "5m", "BB_width_20")
        keltner_upper = self._get(market_state, pair, "5m", "Keltner_upper")
        keltner_lower = self._get(market_state, pair, "5m", "Keltner_lower")
        atr = self._get(market_state, pair, "5m", "ATR_14")
        roc = self._get(market_state, pair, "5m", "ROC_9")
        rsi = self._get(market_state, pair, "5m", "RSI_14")
        macd_hist = self._get(market_state, pair, "5m", "MACD_hist")
        ema_9 = self._get(market_state, pair, "5m", "EMA_9")
        ema_21 = self._get(market_state, pair, "5m", "EMA_21")
        close = self._get(market_state, pair, "5m", "close")
        adx = self._get(market_state, pair, "5m", "ADX_14")

        # --- Squeeze detection ---
        # Primary: BB bands strictly inside Keltner channels
        bb_inside_keltner = (
            keltner_lower > 0
            and keltner_upper > 0
            and bb_lower > keltner_lower
            and bb_upper < keltner_upper
        )
        # Alternative: tight BB width with confirmed low directional movement
        bb_width_squeeze = bb_width < 0.03 and adx < 20

        squeeze_detected = bb_inside_keltner or bb_width_squeeze

        if not squeeze_detected:
            return self._no_signal(pair)

        # --- Direction prediction score (bullish) ---
        direction_score = 0

        if rsi > 50:
            direction_score += 15

        if macd_hist > 0:
            direction_score += 15

        if ema_9 > ema_21:
            direction_score += 10

        if roc > 0:
            direction_score += 10

        bb_range = bb_upper - bb_lower
        if bb_range > 0 and close > (bb_lower + bb_range / 2):
            direction_score += 10

        if direction_score < 35:
            return self._no_signal(pair)

        # --- Build signal ---
        confidence = min(40 + direction_score, 90)

        stop_loss_atr = close - atr * 2.0
        stop_loss = max(bb_lower, stop_loss_atr)

        take_profit_levels = [
            {"price": close + atr * 2, "pct": 0.3},
            {"price": close + atr * 3, "pct": 0.3},
            {"price": close + atr * 5, "pct": 0.4},
        ]

        indicators_used = [
            "BB_upper_20", "BB_lower_20", "BB_width_20",
            "Keltner_upper", "Keltner_lower", "ATR_14",
            "ROC_9", "RSI_14", "MACD_hist",
            "EMA_9", "EMA_21", "close", "ADX_14",
        ]

        reasoning = (
            f"VolatilitySqueeze BUY: squeeze=True, direction_score={direction_score}, "
            f"RSI={rsi:.1f}, MACD_hist={macd_hist:.4f}, EMA_9={ema_9:.4f}, "
            f"EMA_21={ema_21:.4f}, ROC={roc:.4f}, BB_width={bb_width:.4f}, ADX={adx:.1f}"
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
        """Generate an exit signal when squeeze conditions break down unfavourably."""

        close = self._get(market_state, pair, "5m", "close")
        bb_lower = self._get(market_state, pair, "5m", "BB_lower_20")
        bb_width = self._get(market_state, pair, "5m", "BB_width_20")
        ema_21 = self._get(market_state, pair, "5m", "EMA_21")

        # Wrong direction: close dropped below BB lower — full urgent exit
        if bb_lower > 0 and close < bb_lower:
            return ExitSignal(
                should_exit=True,
                urgency=90,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Close below BB lower — squeeze broke wrong direction",
                timestamp=datetime.now(timezone.utc),
            )

        # BB expanding but price below EMA_21 — partial exit
        if bb_width > 0.06 and ema_21 > 0 and close < ema_21:
            return ExitSignal(
                should_exit=True,
                urgency=60,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason=(
                    f"BB expanding (width={bb_width:.4f} > 0.04) "
                    f"but close={close:.4f} < EMA_21={ema_21:.4f} — partial exit"
                ),
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
