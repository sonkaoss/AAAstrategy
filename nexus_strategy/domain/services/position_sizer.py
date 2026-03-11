"""PositionSizer — Kelly Criterion-based position sizing service."""
from __future__ import annotations

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.signal import SignalBundle
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime


class PositionSizer:
    """Calculates position size as a fraction of total capital using the Kelly Criterion."""

    def __init__(self, config: IConfigProvider):
        self._config = config

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def calculate_size(
        self,
        signal_bundle: SignalBundle,
        market_state: MarketState,
        portfolio_state: dict,
    ) -> float:
        """Return position size as a fraction of total capital (0.0 to 0.15).

        Returns 0.0 when the computed size is below the minimum trading
        threshold of 0.05 (5 % of capital).
        """
        half_kelly = self._compute_half_kelly(portfolio_state)

        regime_mult = self._regime_multiplier(market_state)
        confidence_mult = signal_bundle.composite_score / 100.0
        consensus_mult = signal_bundle.suggested_stake_multiplier
        drawdown_mult = self._drawdown_multiplier(portfolio_state)
        correlation_mult = self._correlation_multiplier(portfolio_state)
        sentinel_mult = self._sentinel_multiplier(market_state)

        size = (
            half_kelly
            * regime_mult
            * confidence_mult
            * consensus_mult
            * drawdown_mult
            * correlation_mult
            * sentinel_mult
        )

        if size < 0.05:
            return 0.0

        return min(max(size, 0.05), 0.15)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _compute_half_kelly(self, portfolio_state: dict) -> float:
        """Return the half-Kelly fraction clamped to [0.0, 0.25]."""
        win_rate = portfolio_state.get("win_rate", 0.5)
        avg_win = portfolio_state.get("avg_win", 0.02)
        avg_loss = portfolio_state.get("avg_loss", 0.01)

        if avg_win <= 0:
            return 0.0

        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        half_kelly = max(kelly * 0.5, 0.0)
        return min(half_kelly, 0.25)

    def _regime_multiplier(self, market_state: MarketState) -> float:
        """Return a position-size multiplier based on the synthesized regime."""
        regime: SynthesizedRegime = market_state.regime.synthesized

        if regime in (
            SynthesizedRegime.REGIME_STRONG_BULL,
            SynthesizedRegime.REGIME_BREAKOUT_BULL,
            SynthesizedRegime.REGIME_EUPHORIA,
        ):
            return 1.2
        elif regime == SynthesizedRegime.REGIME_MODERATE_BULL:
            return 1.0
        elif regime in (
            SynthesizedRegime.REGIME_WEAK_BULL,
            SynthesizedRegime.REGIME_ACCUMULATION,
        ):
            return 0.8
        elif regime in (
            SynthesizedRegime.REGIME_RANGING_TIGHT,
            SynthesizedRegime.REGIME_RANGING_WIDE,
            SynthesizedRegime.REGIME_SQUEEZE,
        ):
            return 0.6
        elif regime in (
            SynthesizedRegime.REGIME_WEAK_BEAR,
            SynthesizedRegime.REGIME_TRANSITION_DOWN,
        ):
            return 0.4
        elif regime in (
            SynthesizedRegime.REGIME_STRONG_BEAR,
            SynthesizedRegime.REGIME_MODERATE_BEAR,
            SynthesizedRegime.REGIME_DISTRIBUTION,
        ):
            return 0.3
        elif regime == SynthesizedRegime.REGIME_PANIC:
            return 0.2
        else:
            return 0.5

    def _drawdown_multiplier(self, portfolio_state: dict) -> float:
        """Return a multiplier that reduces size as drawdown increases."""
        current_drawdown_pct = portfolio_state.get("current_drawdown_pct", 0)
        return max(0.1, 1.0 - current_drawdown_pct / 100.0)

    def _correlation_multiplier(self, portfolio_state: dict) -> float:
        """Return a multiplier that reduces size when portfolio correlation is high."""
        max_correlation = portfolio_state.get("max_correlation", 0)
        return max(0.3, 1.0 - max_correlation * 0.5)

    def _sentinel_multiplier(self, market_state: MarketState) -> float:
        """Return a multiplier based on the sentinel risk score."""
        risk = market_state.sentinel.get("risk_score", 0)
        if risk >= 80:
            return 0.3
        elif risk >= 60:
            return 0.7
        else:
            return 1.0
