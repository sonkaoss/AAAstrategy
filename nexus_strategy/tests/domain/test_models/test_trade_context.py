"""Tests for TradeContext domain model."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.trade_context import TradeContext


def _make_trade_context(**kwargs):
    defaults = dict(
        trade_id="trade_001",
        pair="BTC/USDT",
        entry_signal=None,
        entry_regime=None,
        entry_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=45000.0,
        current_avg_price=45000.0,
        total_stake=100.0,
        dca_count=0,
        dca_history=[],
        derisk_count=0,
        derisk_history=[],
        partial_tp_history=[],
        max_profit_reached=0.0,
        max_loss_reached=0.0,
        current_pnl=0.0,
        position_score=50.0,
        time_in_trade_candles=10,
        regime_changes=[],
        trailing_stop_price=44000.0,
        current_trailing_distance=0.02,
        last_validation={},
        strategy_confidence_now=0.7,
    )
    defaults.update(kwargs)
    return TradeContext(**defaults)


class TestTradeContextNotFrozen:
    def test_is_not_frozen(self):
        tc = _make_trade_context()
        tc.current_pnl = 500.0
        assert tc.current_pnl == 500.0

    def test_dca_count_mutable(self):
        tc = _make_trade_context()
        tc.dca_count = 2
        assert tc.dca_count == 2


class TestTradeContextIsProfitable:
    def test_is_profitable_positive_pnl(self):
        tc = _make_trade_context(current_pnl=100.0)
        assert tc.is_profitable is True

    def test_is_profitable_zero_pnl(self):
        tc = _make_trade_context(current_pnl=0.0)
        assert tc.is_profitable is False

    def test_is_profitable_negative_pnl(self):
        tc = _make_trade_context(current_pnl=-50.0)
        assert tc.is_profitable is False


class TestTradeContextSerialization:
    def test_to_custom_data_returns_dict(self):
        tc = _make_trade_context()
        data = tc.to_custom_data()
        assert isinstance(data, dict)

    def test_to_custom_data_serializes_datetime(self):
        tc = _make_trade_context(
            entry_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        data = tc.to_custom_data()
        assert isinstance(data["entry_timestamp"], str)
        assert data["entry_timestamp"] == "2024-01-01T00:00:00+00:00"

    def test_to_custom_data_preserves_simple_fields(self):
        tc = _make_trade_context(trade_id="abc123", pair="ETH/USDT", entry_price=2000.0)
        data = tc.to_custom_data()
        assert data["trade_id"] == "abc123"
        assert data["pair"] == "ETH/USDT"
        assert data["entry_price"] == 2000.0

    def test_to_custom_data_non_serializable_becomes_none(self):
        class NonSerializable:
            pass

        tc = _make_trade_context(entry_signal=NonSerializable())
        data = tc.to_custom_data()
        assert data["entry_signal"] is None

    def test_roundtrip_from_custom_data(self):
        tc = _make_trade_context(
            trade_id="roundtrip_001",
            pair="BTC/USDT",
            entry_price=50000.0,
            current_pnl=200.0,
            entry_timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = tc.to_custom_data()
        tc2 = TradeContext.from_custom_data(data)
        assert tc2.trade_id == tc.trade_id
        assert tc2.pair == tc.pair
        assert tc2.entry_price == tc.entry_price
        assert tc2.current_pnl == tc.current_pnl
        assert tc2.entry_timestamp == tc.entry_timestamp

    def test_from_custom_data_parses_datetime(self):
        tc = _make_trade_context(
            entry_timestamp=datetime(2024, 3, 10, 8, 30, 0, tzinfo=timezone.utc)
        )
        data = tc.to_custom_data()
        tc2 = TradeContext.from_custom_data(data)
        assert tc2.entry_timestamp == datetime(2024, 3, 10, 8, 30, 0, tzinfo=timezone.utc)

    def test_from_custom_data_is_classmethod(self):
        tc = _make_trade_context()
        data = tc.to_custom_data()
        tc2 = TradeContext.from_custom_data(data)
        assert isinstance(tc2, TradeContext)
