"""Signal domain models — immutable data structures for trading signals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any


class ExitLayer(IntEnum):
    """Priority layers for exit signal processing (lower = higher urgency)."""

    EMERGENCY = 1
    TECHNICAL = 2
    REGIME = 3
    PORTFOLIO = 4
    PROFIT_OPTIMIZER = 5


@dataclass(frozen=True)
class Signal:
    """A single strategy's trading signal for a given pair."""

    pair: str
    strategy_name: str
    action: str  # "BUY" or "NO_SIGNAL"
    confidence: int  # 0-100
    entry_price: float
    stop_loss: float
    take_profit_levels: list[dict]
    indicators_used: list[str]
    reasoning: str
    timestamp: datetime

    @property
    def is_buy(self) -> bool:
        """Return True when the signal is an actionable buy."""
        return self.action == "BUY" and self.confidence > 0

    @property
    def stop_loss_pct(self) -> float:
        """Return the stop loss as a fraction of entry price."""
        if self.entry_price == 0:
            return 0.0
        return (self.stop_loss - self.entry_price) / self.entry_price


@dataclass(frozen=True)
class ExitSignal:
    """Signal requesting a full or partial exit from an open position."""

    should_exit: bool
    urgency: int  # 0-100
    exit_layer: ExitLayer
    partial_pct: float  # fraction of position to close (0.0–1.0)
    reason: str
    timestamp: datetime


@dataclass(frozen=True)
class SignalBundle:
    """Aggregated bundle combining signals from multiple strategies."""

    action: str  # "BUY" or "REJECT"
    pair: str
    composite_score: int  # 0-100
    consensus_count: int
    consensus_total: int
    source_signals: list[Any]
    regime: Any
    suggested_stake_multiplier: float
    weighted_stop_loss: float
    merged_take_profits: list[dict]
    risk_rating: str
    reasoning: str
    sentinel_context: dict
    expiry_candles: int
    created_at: datetime

    @property
    def is_buy(self) -> bool:
        """Return True when the bundle recommends a buy."""
        return self.action == "BUY"

    @property
    def is_rejected(self) -> bool:
        """Return True when the bundle has been rejected."""
        return self.action == "REJECT"

    @property
    def is_strong_buy(self) -> bool:
        """Return True for high-conviction buy signals (score >= 70)."""
        return self.is_buy and self.composite_score >= 70

    @property
    def consensus_ratio(self) -> float:
        """Fraction of contributing signals that agreed."""
        if self.consensus_total == 0:
            return 0.0
        return self.consensus_count / self.consensus_total
