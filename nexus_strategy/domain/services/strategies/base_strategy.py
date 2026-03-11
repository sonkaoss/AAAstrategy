"""BaseStrategy — abstract base class for all Nexus sub-strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal


class BaseStrategy(ABC):
    """Common interface for all 7 sub-strategies.

    Each strategy implements generate_signal (entry) and generate_exit_signal
    (exit).  The base class provides helpers for no-signal responses and
    indicator access.
    """

    def __init__(self, name: str, optimal_regimes: list[SynthesizedRegime]) -> None:
        self._name = name
        self._optimal_regimes = list(optimal_regimes)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def optimal_regimes(self) -> list[SynthesizedRegime]:
        return list(self._optimal_regimes)

    def is_active_for_regime(self, regime: SynthesizedRegime) -> bool:
        """Return True if this strategy should run for the given regime."""
        return regime in self._optimal_regimes

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a trading signal for the given pair."""
        ...

    @abstractmethod
    def generate_exit_signal(
        self,
        pair: str,
        market_state: MarketState,
        entry_price: float,
        current_pnl_pct: float,
    ) -> ExitSignal:
        """Generate an exit signal for an open position."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _no_signal(self, pair: str) -> Signal:
        """Return a NO_SIGNAL Signal."""
        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="NO_SIGNAL",
            confidence=0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit_levels=[],
            indicators_used=[],
            reasoning="No signal conditions met",
            timestamp=datetime.now(timezone.utc),
        )

    def _no_exit(self) -> ExitSignal:
        """Return a no-exit ExitSignal."""
        return ExitSignal(
            should_exit=False,
            urgency=0,
            exit_layer=ExitLayer.TECHNICAL,
            partial_pct=0.0,
            reason="",
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _get(
        market_state: MarketState,
        pair: str,
        tf: str,
        key: str,
        default: float = 0.0,
    ) -> float:
        """Shortcut to get an indicator value with a default."""
        val = market_state.get_indicator(pair, tf, key)
        return val if val is not None else default
