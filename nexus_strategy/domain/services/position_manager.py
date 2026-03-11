"""PositionManager — DCA, Derisk, and Buyback position management for the Nexus strategy.

Domain service (hexagonal architecture): no external library imports beyond
stdlib.  Only imports from domain ports and domain models.
"""
from __future__ import annotations

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regimes in which DCA is forbidden
_DCA_FORBIDDEN_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_PANIC,
    SynthesizedRegime.REGIME_STRONG_BEAR,
    SynthesizedRegime.REGIME_DISTRIBUTION,
})

# Regimes treated as bearish for buyback evaluation
_BUYBACK_BEARISH_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_PANIC,
    SynthesizedRegime.REGIME_STRONG_BEAR,
    SynthesizedRegime.REGIME_MODERATE_BEAR,
    SynthesizedRegime.REGIME_DISTRIBUTION,
})

# DCA levels: maps regime set → (thresholds, max_levels)
# Amounts indexed by dca_count: [0.50, 0.30, 0.15, 0.05]
_DCA_AMOUNTS: list[float] = [0.50, 0.30, 0.15, 0.05]

_STRONG_BULL_REGIMES: frozenset[SynthesizedRegime] = frozenset({
    SynthesizedRegime.REGIME_STRONG_BULL,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
    SynthesizedRegime.REGIME_EUPHORIA,
})

_STRONG_BULL_THRESHOLDS: list[float] = [-4.0, -8.0, -12.0, -16.0]
_MODERATE_BULL_THRESHOLDS: list[float] = [-3.0, -6.0, -10.0]
_DEFAULT_THRESHOLDS: list[float] = [-3.0, -5.0]


class PositionManager:
    """Manages DCA, Derisk, and Buyback decisions for open positions."""

    def __init__(self, config: IConfigProvider) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # evaluate_dca
    # ------------------------------------------------------------------

    def evaluate_dca(
        self,
        pair: str,
        market_state: MarketState,
        current_pnl_pct: float,
        dca_count: int,
        regime: SynthesizedRegime,
    ) -> dict | None:
        """Evaluate whether a DCA action should be taken for the given position.

        Parameters
        ----------
        pair:
            Trading pair symbol (e.g. "BTC/USDT").
        market_state:
            Current immutable market snapshot.
        current_pnl_pct:
            Current PnL percentage of the open position (negative = loss).
        dca_count:
            Number of DCA actions already taken for this position.
        regime:
            Current synthesized market regime.

        Returns
        -------
        dict with keys {"action", "amount_pct", "reason"} or None if no DCA.
        """
        # Forbidden regimes — never DCA
        if regime in _DCA_FORBIDDEN_REGIMES:
            return None

        # Determine thresholds and max levels by regime
        if regime in _STRONG_BULL_REGIMES:
            thresholds = _STRONG_BULL_THRESHOLDS
        elif regime == SynthesizedRegime.REGIME_MODERATE_BULL:
            thresholds = _MODERATE_BULL_THRESHOLDS
        else:
            thresholds = _DEFAULT_THRESHOLDS

        max_levels = len(thresholds)

        # Max DCA levels already reached
        if dca_count >= max_levels:
            return None

        # PnL must be at or below the threshold for this DCA level
        if current_pnl_pct > thresholds[dca_count]:
            return None

        # RSI filter: block DCA if RSI_14 on 5m is >= 40 (not oversold enough)
        rsi = market_state.get_indicator(pair, "5m", "RSI_14")
        if rsi is not None and rsi >= 40.0:
            return None

        amount_pct = _DCA_AMOUNTS[dca_count]
        reason = (
            f"DCA level {dca_count + 1}: PnL {current_pnl_pct:.1f}% "
            f"<= {thresholds[dca_count]:.0f}% threshold"
        )
        return {
            "action": "DCA",
            "amount_pct": amount_pct,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # evaluate_derisk
    # ------------------------------------------------------------------

    def evaluate_derisk(
        self,
        pair: str,
        current_pnl_pct: float,
        rsi: float | None,
    ) -> dict | None:
        """Evaluate whether a partial sell (derisk) should be taken.

        Parameters
        ----------
        pair:
            Trading pair symbol.
        current_pnl_pct:
            Current PnL percentage (negative = loss).
        rsi:
            Current RSI value (any timeframe), or None if unavailable.

        Returns
        -------
        dict with keys {"action", "sell_pct", "level", "reason"} or None.
        """
        # Level 4 — severe loss
        if current_pnl_pct <= -16.0:
            return {
                "action": "DERISK",
                "sell_pct": 0.80,
                "level": 4,
                "reason": "Derisk L4: severe loss",
            }

        # Level 3 — heavy loss
        if current_pnl_pct <= -12.0:
            return {
                "action": "DERISK",
                "sell_pct": 0.40,
                "level": 3,
                "reason": "Derisk L3: heavy loss",
            }

        # Level 2 — significant loss
        if current_pnl_pct <= -8.0:
            return {
                "action": "DERISK",
                "sell_pct": 0.25,
                "level": 2,
                "reason": "Derisk L2: significant loss",
            }

        # Level 1 — skip if RSI < 30 (too oversold, might bounce)
        if current_pnl_pct <= -5.0:
            if rsi is not None and rsi < 30.0:
                return None
            return {
                "action": "DERISK",
                "sell_pct": 0.15,
                "level": 1,
                "reason": "Derisk L1: moderate loss",
            }

        return None

    # ------------------------------------------------------------------
    # evaluate_buyback
    # ------------------------------------------------------------------

    def evaluate_buyback(
        self,
        pair: str,
        prev_profitable: bool,
        price_drop_pct: float,
        regime: SynthesizedRegime,
        confidence: float,
    ) -> dict | None:
        """Evaluate whether to buy back a previously closed profitable position.

        Parameters
        ----------
        pair:
            Trading pair symbol.
        prev_profitable:
            Whether the previously closed trade was profitable.
        price_drop_pct:
            Percentage the price has dropped since the last close (positive = drop).
        regime:
            Current synthesized market regime.
        confidence:
            Confidence score (0-100) for the current regime.

        Returns
        -------
        dict with keys {"action", "size_pct", "reason"} or None.
        """
        # All conditions must be met
        if not prev_profitable:
            return None

        if price_drop_pct <= 3.0:
            return None

        if regime in _BUYBACK_BEARISH_REGIMES:
            return None

        size_pct = 0.8 if confidence > 80 else 0.6
        reason = f"Buyback: price dropped {price_drop_pct:.1f}%"

        return {
            "action": "BUYBACK",
            "size_pct": size_pct,
            "reason": reason,
        }
