"""Risk domain models — mutable data structures for portfolio and position risk."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class DrawdownLevel(IntEnum):
    """Categorical drawdown severity levels."""

    NORMAL = 1
    CAUTION = 2
    WARNING = 3
    CRITICAL = 4
    CATASTROPHIC = 5

    @classmethod
    def from_drawdown(cls, dd: float) -> DrawdownLevel:
        """Classify a numeric drawdown fraction into a severity level.

        Args:
            dd: Drawdown as a positive fraction (e.g. 0.10 = 10% drawdown).

        Returns:
            The corresponding DrawdownLevel.
        """
        if dd < 0.05:
            return cls.NORMAL
        if dd < 0.10:
            return cls.CAUTION
        if dd < 0.15:
            return cls.WARNING
        if dd < 0.20:
            return cls.CRITICAL
        return cls.CATASTROPHIC


@dataclass
class PositionAction:
    """Recommended action for an individual open position (mutable for in-place updates)."""

    action: str
    amount: float
    reason: str
    urgency: int  # 0-100


@dataclass
class PortfolioState:
    """Current snapshot of the portfolio risk state (mutable for in-place updates)."""

    total_equity: float
    peak_equity: float
    current_drawdown: float
    drawdown_level: DrawdownLevel
    open_positions: list[dict]
    total_exposure: float
    cash_available: float
    var_95: float
    cvar_95: float
    correlation_matrix: dict
    sector_distribution: dict
    recovery_mode: bool
    recovery_progress: float

    @property
    def exposure_ratio(self) -> float:
        """Fraction of equity currently deployed in open positions."""
        if self.total_equity == 0:
            return 0.0
        return self.total_exposure / self.total_equity
