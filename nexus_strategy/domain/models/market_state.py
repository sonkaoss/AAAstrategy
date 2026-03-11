"""MarketState domain model — immutable snapshot of the full market environment."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from nexus_strategy.domain.models.regime import CompositeRegime

#: Data older than this many seconds is considered stale.
SENTINEL_STALE_THRESHOLD_SECONDS: int = 300


@dataclass(frozen=True)
class MarketState:
    """Immutable snapshot of market conditions at a given point in time."""

    timestamp: datetime

    # Per-pair indicator values: {pair: {timeframe: {indicator: value}}}
    indicators: dict[str, dict[str, dict[str, float]]]

    # Higher-level composite indicator values: {pair: {indicator: value}}
    composite_indicators: dict[str, dict[str, float]]

    # Regime
    regime: CompositeRegime
    previous_regime: CompositeRegime
    regime_just_changed: bool

    # External sentinel service
    sentinel: dict
    sentinel_connected: bool
    sentinel_data_age_seconds: int

    # BTC macro context
    btc_price: float
    btc_change_1h: float
    btc_change_24h: float
    btc_above_ema200: bool
    btc_trend: str

    # Macro market context
    market_phase: str
    altcoin_season_index: int
    fear_greed: int

    # Weighting maps
    indicator_weights: dict[str, float]
    strategy_weights: dict[str, dict[str, float]]
    indicator_reliability: dict[str, float]

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def sentinel_is_stale(self) -> bool:
        """Return True when the sentinel data is older than the stale threshold."""
        return self.sentinel_data_age_seconds > SENTINEL_STALE_THRESHOLD_SECONDS

    def get_indicator(self, pair: str, tf: str, indicator: str) -> Optional[float]:
        """Return the value for a specific indicator, or ``None`` if not found."""
        try:
            return self.indicators[pair][tf][indicator]
        except KeyError:
            return None
