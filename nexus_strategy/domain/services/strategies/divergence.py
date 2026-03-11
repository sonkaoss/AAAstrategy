"""DivergenceStrategy sub-strategy for the Nexus trading system."""
from __future__ import annotations

from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

_OPTIMAL_REGIMES: list[SynthesizedRegime] = [
    SynthesizedRegime.REGIME_WEAK_BEAR,
    SynthesizedRegime.REGIME_ACCUMULATION,
    SynthesizedRegime.REGIME_TRANSITION_UP,
]


class DivergenceStrategy(BaseStrategy):
    """Divergence strategy detecting bullish divergence signals during weak bear / accumulation phases."""

    def __init__(self) -> None:
        super().__init__(name="Divergence", optimal_regimes=_OPTIMAL_REGIMES)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_indicators(self, market_state: MarketState, pair: str, tf: str) -> dict:
        """Fetch all required indicators for a given timeframe."""
        return {
            "rsi": self._get(market_state, pair, tf, "RSI_14"),
            "macd": self._get(market_state, pair, tf, "MACD_12_26_9"),
            "macd_hist": self._get(market_state, pair, tf, "MACDh_12_26_9"),
            "cci": self._get(market_state, pair, tf, "CCI_20"),
            "mfi": self._get(market_state, pair, tf, "MFI_14"),
            "close": self._get(market_state, pair, tf, "close"),
            "ema_21": self._get(market_state, pair, tf, "EMA_21"),
            "ema_50": self._get(market_state, pair, tf, "EMA_50"),
            "bb_lower": self._get(market_state, pair, tf, "BB_lower_20"),
            "bb_upper": self._get(market_state, pair, tf, "BB_upper_20"),
            "cmf": self._get(market_state, pair, tf, "CMF_20"),
            "atr": self._get(market_state, pair, tf, "ATR_14"),
        }

    def _detect_divergences(self, ind: dict) -> dict[str, bool]:
        """Detect individual bullish divergence conditions.

        Returns a mapping of divergence name -> whether the condition is active.
        """
        close = ind["close"]
        ema_21 = ind["ema_21"]
        ema_50 = ind["ema_50"]
        rsi = ind["rsi"]
        macd = ind["macd"]
        macd_hist = ind["macd_hist"]
        cmf = ind["cmf"]
        cci = ind["cci"]
        bb_lower = ind["bb_lower"]
        mfi = ind["mfi"]

        return {
            "rsi_div": close < ema_21 and rsi > 40,
            "macd_div": close < ema_21 and (macd > 0 or macd_hist > 0),
            "volume_div": cmf > 0 and close < ema_50,
            "cci_div": cci > -50 and bb_lower > 0 and close < bb_lower,
            "mfi_div": mfi > 40 and close < ema_21,
        }

    def _score_divergences(self, divs: dict[str, bool]) -> int:
        """Convert detected divergences into a numeric score."""
        score = 0
        if divs.get("rsi_div"):
            score += 20
        if divs.get("macd_div"):
            score += 20
        if divs.get("volume_div"):
            score += 15
        if divs.get("cci_div"):
            score += 15
        if divs.get("mfi_div"):
            score += 10
        return score

    # ------------------------------------------------------------------
    # Entry signal
    # ------------------------------------------------------------------

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a BUY signal when bullish divergence conditions are detected."""

        ind_5m = self._fetch_indicators(market_state, pair, "5m")
        ind_15m = self._fetch_indicators(market_state, pair, "15m")

        close = ind_5m["close"]

        # Bail early when no meaningful price data is present.
        if close <= 0:
            return self._no_signal(pair)

        # --- Detect divergences on each timeframe ---
        divs_5m = self._detect_divergences(ind_5m)
        divs_15m = self._detect_divergences(ind_15m)

        score_5m = self._score_divergences(divs_5m)

        # --- Multi-TF confirmation ---
        matching_tfs = sum(
            1
            for key in divs_5m
            if divs_5m[key] and divs_15m.get(key)
        )

        score = score_5m
        if matching_tfs >= 2:
            score = int(score * 1.3)

        if score < 50:
            return self._no_signal(pair)

        # --- Build signal ---
        confidence = min(score, 90)

        ema_21 = ind_5m["ema_21"]
        ema_50 = ind_5m["ema_50"]
        bb_lower = ind_5m["bb_lower"]
        bb_upper = ind_5m["bb_upper"]
        atr = ind_5m["atr"]

        stop_loss = close - atr * 2.5

        bb_mid = bb_lower + (bb_upper - bb_lower) * 0.5
        take_profit_levels = [
            {"price": ema_21, "pct": 0.3},
            {"price": ema_50, "pct": 0.3},
            {"price": bb_mid, "pct": 0.4},
        ]

        active_5m = [k for k, v in divs_5m.items() if v]
        reasoning = (
            f"Divergence BUY: score={score}, close={close:.4f}, "
            f"RSI={ind_5m['rsi']:.1f}, MACD={ind_5m['macd']:.4f}, "
            f"CMF={ind_5m['cmf']:.3f}, CCI={ind_5m['cci']:.1f}, "
            f"MFI={ind_5m['mfi']:.1f}, active_divs={active_5m}, "
            f"multi_tf_matches={matching_tfs}"
        )

        indicators_used = [
            "RSI_14", "MACD_12_26_9", "MACDh_12_26_9", "CCI_20", "MFI_14",
            "close", "EMA_21", "EMA_50", "BB_lower_20", "BB_upper_20",
            "CMF_20", "ATR_14",
        ]

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
        """Generate an exit signal when divergence conditions are exhausted."""

        rsi = self._get(market_state, pair, "5m", "RSI_14")
        close = self._get(market_state, pair, "5m", "close")
        ema_50 = self._get(market_state, pair, "5m", "EMA_50")

        # No meaningful price data — skip all exit checks.
        if close <= 0:
            return self._no_exit()

        # Divergence resolved: RSI overbought and price above EMA_50
        if rsi > 65 and close > ema_50:
            return ExitSignal(
                should_exit=True,
                urgency=50,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason=f"Divergence resolved: RSI={rsi:.1f} > 65 and close > EMA_50",
                timestamp=datetime.now(timezone.utc),
            )

        # Stop loss hit: price 3% below entry
        if entry_price > 0 and close < entry_price * 0.97:
            return ExitSignal(
                should_exit=True,
                urgency=80,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason=f"Stop loss hit: close={close:.4f} is 3%+ below entry={entry_price:.4f}",
                timestamp=datetime.now(timezone.utc),
            )

        return self._no_exit()
