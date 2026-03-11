"""ExitEngine — 5-layer exit system for the Nexus trading strategy."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal
from nexus_strategy.domain.ports.config_port import IConfigProvider

# Doom-stop thresholds keyed by synthesized regime.
_DOOM_THRESHOLDS: dict[SynthesizedRegime, float] = {
    SynthesizedRegime.REGIME_PANIC: -4.0,
    SynthesizedRegime.REGIME_STRONG_BEAR: -6.0,
    SynthesizedRegime.REGIME_MODERATE_BEAR: -8.0,
    SynthesizedRegime.REGIME_RANGING_TIGHT: -10.0,
    SynthesizedRegime.REGIME_RANGING_WIDE: -10.0,
    SynthesizedRegime.REGIME_CHOPPY: -10.0,
    SynthesizedRegime.REGIME_MODERATE_BULL: -12.0,
    SynthesizedRegime.REGIME_WEAK_BULL: -12.0,
    SynthesizedRegime.REGIME_STRONG_BULL: -15.0,
    SynthesizedRegime.REGIME_BREAKOUT_BULL: -15.0,
    SynthesizedRegime.REGIME_EUPHORIA: -15.0,
}

_DEFAULT_DOOM_THRESHOLD: float = -10.0

# Bearish regimes that trigger a Layer-3 regime-change exit.
_BEARISH_EXIT_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_STRONG_BEAR,
    SynthesizedRegime.REGIME_MODERATE_BEAR,
    SynthesizedRegime.REGIME_PANIC,
    SynthesizedRegime.REGIME_DISTRIBUTION,
})


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class ExitEngine:
    """Evaluates five priority layers to decide whether a position should be exited."""

    def __init__(self, config: IConfigProvider) -> None:
        self._config = config

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        pair: str,
        market_state: MarketState,
        entry_price: float,
        current_pnl_pct: float,
        position_age_candles: int,
        strategy_exit_signals: list[ExitSignal],
        portfolio_state: dict,
    ) -> Optional[ExitSignal]:
        """Return the highest-urgency exit signal across all five layers, or *None*."""

        candidates: list[ExitSignal] = []

        candidates.extend(self._layer_emergency(current_pnl_pct, market_state, portfolio_state))
        candidates.extend(self._layer_technical(pair, market_state, strategy_exit_signals))
        candidates.extend(self._layer_regime(market_state))
        candidates.extend(self._layer_portfolio(portfolio_state))
        candidates.extend(self._layer_profit_optimizer(current_pnl_pct, position_age_candles))

        if not candidates:
            return None

        return max(candidates, key=lambda s: s.urgency)

    # ------------------------------------------------------------------ #
    # Layer 1 — Emergency                                                 #
    # ------------------------------------------------------------------ #

    def _layer_emergency(
        self,
        pnl_pct: float,
        market_state: MarketState,
        portfolio_state: dict,
    ) -> list[ExitSignal]:
        signals: list[ExitSignal] = []

        # Black Swan
        if pnl_pct < -10:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=100,
                exit_layer=ExitLayer.EMERGENCY,
                partial_pct=1.0,
                reason="Black Swan: extreme loss",
                timestamp=_now(),
            ))

        # Doom stop (regime-adaptive)
        threshold = _DOOM_THRESHOLDS.get(
            market_state.regime.synthesized,
            _DEFAULT_DOOM_THRESHOLD,
        )
        if pnl_pct <= threshold:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=95,
                exit_layer=ExitLayer.EMERGENCY,
                partial_pct=1.0,
                reason=f"Doom stop at {threshold}%",
                timestamp=_now(),
            ))

        # Portfolio-level protection
        if portfolio_state.get("total_pnl_pct", 0) < -20:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=100,
                exit_layer=ExitLayer.EMERGENCY,
                partial_pct=1.0,
                reason="Portfolio protection: extreme drawdown",
                timestamp=_now(),
            ))

        return signals

    # ------------------------------------------------------------------ #
    # Layer 2 — Technical                                                 #
    # ------------------------------------------------------------------ #

    def _layer_technical(
        self,
        pair: str,
        market_state: MarketState,
        strategy_exit_signals: list[ExitSignal],
    ) -> list[ExitSignal]:
        signals: list[ExitSignal] = []

        # Strategy-independent indicator checks (5m timeframe)
        rsi = market_state.get_indicator(pair, "5m", "RSI")
        if rsi is not None and rsi > 78:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=55,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="RSI extreme overbought",
                timestamp=_now(),
            ))

        ema_9 = market_state.get_indicator(pair, "5m", "EMA_9")
        ema_21 = market_state.get_indicator(pair, "5m", "EMA_21")
        ema_50 = market_state.get_indicator(pair, "5m", "EMA_50")
        if (
            ema_9 is not None
            and ema_21 is not None
            and ema_50 is not None
            and ema_9 < ema_21
            and ema_21 < ema_50
        ):
            signals.append(ExitSignal(
                should_exit=True,
                urgency=65,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Triple EMA bearish cross",
                timestamp=_now(),
            ))

        # Aggregate strategy exit signals (those with should_exit=True)
        active = [s for s in strategy_exit_signals if s.should_exit]
        total_active = len(active) + len(signals)  # indicator signals count too

        if total_active >= 4:
            max_urgency = max(
                (s.urgency for s in active),
                default=0,
            )
            # Also consider indicator-based signal urgencies
            if signals:
                max_urgency = max(max_urgency, max(s.urgency for s in signals))
            signals.append(ExitSignal(
                should_exit=True,
                urgency=max_urgency,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=1.0,
                reason="Multiple technical exits: full close",
                timestamp=_now(),
            ))
        elif 2 <= total_active <= 3:
            max_urgency = max(
                (s.urgency for s in active),
                default=0,
            )
            if signals:
                max_urgency = max(max_urgency, max(s.urgency for s in signals))
            signals.append(ExitSignal(
                should_exit=True,
                urgency=max_urgency,
                exit_layer=ExitLayer.TECHNICAL,
                partial_pct=0.5,
                reason="Multiple technical exits: partial close",
                timestamp=_now(),
            ))
        elif total_active == 1:
            # When a single active signal and no indicator signals, use the strategy signal
            if active and not signals:
                s = active[0]
                signals.append(ExitSignal(
                    should_exit=True,
                    urgency=s.urgency,
                    exit_layer=ExitLayer.TECHNICAL,
                    partial_pct=0.25,
                    reason=s.reason,
                    timestamp=_now(),
                ))
            # When only an indicator signal fired, it's already in signals list

        return signals

    # ------------------------------------------------------------------ #
    # Layer 3 — Regime                                                    #
    # ------------------------------------------------------------------ #

    def _layer_regime(self, market_state: MarketState) -> list[ExitSignal]:
        signals: list[ExitSignal] = []

        # Regime just changed to a bearish regime
        if (
            market_state.regime_just_changed
            and market_state.regime.synthesized in _BEARISH_EXIT_REGIMES
        ):
            signals.append(ExitSignal(
                should_exit=True,
                urgency=70,
                exit_layer=ExitLayer.REGIME,
                partial_pct=0.5,
                reason="Regime turned bearish",
                timestamp=_now(),
            ))

        # Sentinel risk override
        risk_score = market_state.sentinel.get("risk_score", 0)
        if risk_score >= 90:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=80,
                exit_layer=ExitLayer.REGIME,
                partial_pct=1.0,
                reason="Sentinel risk critical",
                timestamp=_now(),
            ))

        return signals

    # ------------------------------------------------------------------ #
    # Layer 4 — Portfolio                                                 #
    # ------------------------------------------------------------------ #

    def _layer_portfolio(self, portfolio_state: dict) -> list[ExitSignal]:
        signals: list[ExitSignal] = []

        drawdown_level = portfolio_state.get("drawdown_level", 0)
        if drawdown_level >= 4:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=85,
                exit_layer=ExitLayer.PORTFOLIO,
                partial_pct=1.0,
                reason="Catastrophic drawdown",
                timestamp=_now(),
            ))
        elif drawdown_level >= 3:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=70,
                exit_layer=ExitLayer.PORTFOLIO,
                partial_pct=0.5,
                reason="Critical drawdown",
                timestamp=_now(),
            ))

        if portfolio_state.get("slots_exceeded", False):
            signals.append(ExitSignal(
                should_exit=True,
                urgency=50,
                exit_layer=ExitLayer.PORTFOLIO,
                partial_pct=0.25,
                reason="Position slots exceeded",
                timestamp=_now(),
            ))

        return signals

    # ------------------------------------------------------------------ #
    # Layer 5 — Profit Optimizer                                          #
    # ------------------------------------------------------------------ #

    def _layer_profit_optimizer(
        self,
        pnl_pct: float,
        position_age_candles: int,
    ) -> list[ExitSignal]:
        signals: list[ExitSignal] = []

        if pnl_pct >= 8:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=40,
                exit_layer=ExitLayer.PROFIT_OPTIMIZER,
                partial_pct=0.25,
                reason="TP Level 4",
                timestamp=_now(),
            ))
        elif pnl_pct >= 5:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=35,
                exit_layer=ExitLayer.PROFIT_OPTIMIZER,
                partial_pct=0.25,
                reason="TP Level 3",
                timestamp=_now(),
            ))
        elif pnl_pct >= 3:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=30,
                exit_layer=ExitLayer.PROFIT_OPTIMIZER,
                partial_pct=0.25,
                reason="TP Level 2",
                timestamp=_now(),
            ))
        elif pnl_pct >= 1.5:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=25,
                exit_layer=ExitLayer.PROFIT_OPTIMIZER,
                partial_pct=0.25,
                reason="TP Level 1",
                timestamp=_now(),
            ))

        # Time decay
        if position_age_candles > 72 and pnl_pct < 1:
            signals.append(ExitSignal(
                should_exit=True,
                urgency=45,
                exit_layer=ExitLayer.PROFIT_OPTIMIZER,
                partial_pct=0.5,
                reason="Time decay",
                timestamp=_now(),
            ))

        return signals
