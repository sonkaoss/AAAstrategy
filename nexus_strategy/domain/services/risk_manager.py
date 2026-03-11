"""RiskManager — Portfolio-level risk management service."""
from __future__ import annotations

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.signal import SignalBundle
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import SynthesizedRegime
from nexus_strategy.utils.constants import SECTOR_MAP

# Drawdown level constants
_DRAWDOWN_NORMAL = 0        # < 5%
_DRAWDOWN_CAUTION = 1       # 5–10%
_DRAWDOWN_WARNING = 2       # 10–15%
_DRAWDOWN_CRITICAL = 3      # 15–20%
_DRAWDOWN_CATASTROPHIC = 4  # > 20%


class RiskManager:
    """Portfolio-level risk gate: validates entries and measures portfolio risk."""

    def __init__(self, config: IConfigProvider):
        self._config = config

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def validate_entry(
        self,
        signal_bundle: SignalBundle,
        market_state: MarketState,
        portfolio_state: dict,
    ) -> tuple[bool, str]:
        """Validate whether a new position entry is permitted.

        Returns
        -------
        (allowed, reason)
            allowed is False when one of the rejection conditions is met,
            True when all checks pass.
        """
        drawdown_pct = portfolio_state.get("current_drawdown_pct", 0.0)
        drawdown_level = self.get_drawdown_level(drawdown_pct)

        # 1. Catastrophic drawdown — no entries at all
        if drawdown_level >= 4:
            return (False, "Catastrophic drawdown - no entries")

        # 2. Critical drawdown — only high-confidence entries
        if drawdown_level >= 3 and signal_bundle.composite_score <= 80:
            return (False, "Critical drawdown - only high confidence entries")

        # 3. Maximum position slots reached
        open_positions = portfolio_state.get("open_positions", 0)
        regime = market_state.regime.synthesized
        max_slots = self.get_max_slots(regime)
        if open_positions >= max_slots:
            return (False, "Maximum position slots reached")

        # 4. Pair already has an open position
        open_pairs: list[str] = portfolio_state.get("open_pairs", [])
        if signal_bundle.pair in open_pairs:
            return (False, "Pair already has open position")

        # 5. Maximum portfolio exposure reached
        total_exposure = portfolio_state.get("total_exposure", 0.0)
        if total_exposure >= 0.85:
            return (False, "Maximum portfolio exposure reached")

        # 6. Sentinel risk score too high
        sentinel_risk = market_state.sentinel.get("risk_score", 0)
        if sentinel_risk >= 80:
            return (False, "Sentinel risk too high")

        # 7. Sector concentration limit reached
        pair_sector = self._get_sector(signal_bundle.pair)
        sector_exposures: dict[str, float] = portfolio_state.get("sector_exposure", {})
        if pair_sector is not None and sector_exposures.get(pair_sector, 0.0) >= 0.35:
            return (False, "Sector concentration limit reached")

        return (True, "Entry allowed")

    def get_drawdown_level(self, current_drawdown_pct: float) -> int:
        """Return the drawdown severity level (0–4) for a given drawdown percentage.

        Parameters
        ----------
        current_drawdown_pct:
            Current portfolio drawdown expressed as a positive percentage
            (e.g. 12.0 means –12 %).

        Returns
        -------
        int
            0 = NORMAL, 1 = CAUTION, 2 = WARNING, 3 = CRITICAL, 4 = CATASTROPHIC
        """
        if current_drawdown_pct < 5:
            return _DRAWDOWN_NORMAL
        elif current_drawdown_pct < 10:
            return _DRAWDOWN_CAUTION
        elif current_drawdown_pct < 15:
            return _DRAWDOWN_WARNING
        elif current_drawdown_pct < 20:
            return _DRAWDOWN_CRITICAL
        else:
            return _DRAWDOWN_CATASTROPHIC

    def get_max_slots(self, regime: SynthesizedRegime) -> int:
        """Return the maximum number of simultaneous open positions for a regime."""
        if regime in (
            SynthesizedRegime.REGIME_STRONG_BULL,
            SynthesizedRegime.REGIME_BREAKOUT_BULL,
            SynthesizedRegime.REGIME_EUPHORIA,
        ):
            return 12
        elif regime == SynthesizedRegime.REGIME_MODERATE_BULL:
            return 10
        elif regime in (
            SynthesizedRegime.REGIME_WEAK_BULL,
            SynthesizedRegime.REGIME_ACCUMULATION,
            SynthesizedRegime.REGIME_RANGING_TIGHT,
            SynthesizedRegime.REGIME_RANGING_WIDE,
        ):
            return 8
        elif regime in (
            SynthesizedRegime.REGIME_WEAK_BEAR,
            SynthesizedRegime.REGIME_MODERATE_BEAR,
            SynthesizedRegime.REGIME_TRANSITION_DOWN,
        ):
            return 5
        elif regime == SynthesizedRegime.REGIME_PANIC:
            return 2
        else:
            return 8

    def calculate_portfolio_risk(self, positions: list[dict]) -> dict:
        """Calculate aggregate portfolio risk metrics.

        Parameters
        ----------
        positions:
            List of position dicts with keys ``pair`` (str), ``size`` (float),
            and ``pnl_pct`` (float).

        Returns
        -------
        dict
            Keys: ``total_exposure``, ``var_95``, ``sector_distribution``,
            ``position_count``.
        """
        if not positions:
            return {
                "total_exposure": 0,
                "var_95": 0,
                "sector_distribution": {},
                "position_count": 0,
            }

        total_exposure = sum(pos["size"] for pos in positions)
        var_95 = -2.0 * total_exposure

        sector_distribution: dict[str, int] = {}
        for pos in positions:
            sector = self._get_sector(pos["pair"])
            if sector is not None:
                sector_distribution[sector] = sector_distribution.get(sector, 0) + 1

        return {
            "total_exposure": total_exposure,
            "var_95": var_95,
            "sector_distribution": sector_distribution,
            "position_count": len(positions),
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_sector(pair: str) -> str | None:
        """Return the sector for *pair*, or None if not in SECTOR_MAP."""
        return SECTOR_MAP.get(pair)
