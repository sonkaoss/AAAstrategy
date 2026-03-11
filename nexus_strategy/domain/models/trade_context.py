"""TradeContext domain model — mutable runtime state for a single open trade."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _serialize_value(v: Any) -> Any:
    """Convert a value to a JSON-compatible type, returning None for unknowns."""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (str, int, float, bool, type(None))):
        return v
    if isinstance(v, dict):
        return {k: _serialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_serialize_value(item) for item in v]
    # Non-serializable objects are stored as None
    return None


def _deserialize_value(v: Any) -> Any:
    """Inverse of _serialize_value; converts ISO strings back to datetime where appropriate."""
    if isinstance(v, str):
        # Attempt datetime parse; keep as string if it fails
        try:
            return datetime.fromisoformat(v)
        except (ValueError, TypeError):
            return v
    if isinstance(v, dict):
        return {k: _deserialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_deserialize_value(item) for item in v]
    return v


@dataclass
class TradeContext:
    """Mutable runtime context for a single open trade, tracking all lifecycle events."""

    trade_id: str
    pair: str
    entry_signal: Any
    entry_regime: Any
    entry_timestamp: datetime
    entry_price: float
    current_avg_price: float
    total_stake: float
    dca_count: int
    dca_history: list[dict]
    derisk_count: int
    derisk_history: list[dict]
    partial_tp_history: list[dict]
    max_profit_reached: float
    max_loss_reached: float
    current_pnl: float
    position_score: float
    time_in_trade_candles: int
    regime_changes: list[dict]
    trailing_stop_price: float
    current_trailing_distance: float
    last_validation: dict
    strategy_confidence_now: float

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def is_profitable(self) -> bool:
        """Return True when the trade is currently in profit."""
        return self.current_pnl > 0

    # ------------------------------------------------------------------ #
    # Serialization helpers                                                #
    # ------------------------------------------------------------------ #

    def to_custom_data(self) -> dict:
        """Serialize the context to a JSON-compatible dictionary.

        ``datetime`` values are converted to ISO-format strings.  Any
        field whose value cannot be serialised (e.g. complex objects) is
        stored as ``None``.
        """
        result: dict = {}
        for field_name, value in self.__dict__.items():
            result[field_name] = _serialize_value(value)
        return result

    @classmethod
    def from_custom_data(cls, data: dict) -> TradeContext:
        """Deserialize a dictionary produced by :meth:`to_custom_data`.

        ISO-format datetime strings stored in ``entry_timestamp`` are
        converted back to :class:`datetime` objects.  All other string
        fields are left untouched.
        """
        processed: dict = {}
        for key, value in data.items():
            # Only attempt datetime conversion for the dedicated timestamp field.
            if key == "entry_timestamp" and isinstance(value, str):
                try:
                    processed[key] = datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    processed[key] = value
            else:
                processed[key] = value
        return cls(**processed)
