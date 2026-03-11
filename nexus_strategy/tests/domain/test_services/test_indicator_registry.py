"""Tests for the IndicatorRegistry service."""
from __future__ import annotations

import pytest

from nexus_strategy.domain.services.indicator_registry import (
    IndicatorSpec,
    IndicatorRegistry,
)


class TestIndicatorSpec:
    def test_is_dataclass(self):
        from dataclasses import fields
        assert len(fields(IndicatorSpec)) > 0

    def test_not_frozen(self):
        spec = IndicatorSpec(
            name="TEST",
            category="momentum",
            timeframes=["5m"],
            params={"period": 14},
        )
        spec.weight = 2.0  # should not raise
        assert spec.weight == 2.0

    def test_defaults(self):
        spec = IndicatorSpec(
            name="TEST",
            category="momentum",
            timeframes=["5m"],
            params={},
        )
        assert spec.weight == 1.0
        assert spec.reliability == 0.5
        assert spec.signal_count == 0
        assert spec.correct_count == 0


class TestIndicatorRegistryDefaults:
    def setup_method(self):
        self.registry = IndicatorRegistry()

    def test_default_indicators_registered(self):
        assert len(self.registry.get_all()) >= 33

    def test_get_existing(self):
        assert self.registry.get("RSI_14") is not None

    def test_get_missing(self):
        assert self.registry.get("NONEXIST") is None

    def test_get_by_category_momentum(self):
        momentum = self.registry.get_by_category("momentum")
        assert len(momentum) >= 7

    def test_get_by_category_trend(self):
        trend = self.registry.get_by_category("trend")
        assert len(trend) >= 10

    def test_get_by_category_volatility(self):
        volatility = self.registry.get_by_category("volatility")
        assert len(volatility) >= 7

    def test_get_by_category_volume(self):
        volume = self.registry.get_by_category("volume")
        assert len(volume) >= 3

    def test_get_by_category_statistical(self):
        statistical = self.registry.get_by_category("statistical")
        assert len(statistical) >= 2

    def test_get_by_category_empty(self):
        result = self.registry.get_by_category("nonexistent_category")
        assert result == []

    def test_rsi_14_fields(self):
        spec = self.registry.get("RSI_14")
        assert spec is not None
        assert spec.category == "momentum"
        assert "5m" in spec.timeframes
        assert spec.params == {"period": 14}


class TestIndicatorRegistryRegister:
    def setup_method(self):
        self.registry = IndicatorRegistry()

    def test_register_custom(self):
        spec = IndicatorSpec(
            name="CUSTOM_IND",
            category="momentum",
            timeframes=["1h"],
            params={"period": 20},
        )
        self.registry.register(spec)
        retrieved = self.registry.get("CUSTOM_IND")
        assert retrieved is not None
        assert retrieved.name == "CUSTOM_IND"
        assert retrieved.category == "momentum"

    def test_register_appears_in_get_all(self):
        before_count = len(self.registry.get_all())
        spec = IndicatorSpec(
            name="NEW_INDICATOR",
            category="trend",
            timeframes=["5m"],
            params={},
        )
        self.registry.register(spec)
        assert len(self.registry.get_all()) == before_count + 1

    def test_register_appears_in_get_by_category(self):
        before_count = len(self.registry.get_by_category("statistical"))
        spec = IndicatorSpec(
            name="STAT_EXTRA",
            category="statistical",
            timeframes=["1h"],
            params={"period": 30},
        )
        self.registry.register(spec)
        assert len(self.registry.get_by_category("statistical")) == before_count + 1


class TestUpdatePerformance:
    def setup_method(self):
        self.registry = IndicatorRegistry()

    def test_update_performance_correct(self):
        self.registry.update_performance("RSI_14", was_correct=True)
        spec = self.registry.get("RSI_14")
        assert spec is not None
        assert spec.signal_count == 1
        assert spec.correct_count == 1
        assert spec.reliability == pytest.approx(1.0)

    def test_update_performance_incorrect(self):
        self.registry.update_performance("RSI_14", was_correct=False)
        spec = self.registry.get("RSI_14")
        assert spec is not None
        assert spec.signal_count == 1
        assert spec.correct_count == 0
        assert spec.reliability == pytest.approx(0.0)

    def test_update_performance_mixed(self):
        self.registry.update_performance("RSI_14", was_correct=True)
        self.registry.update_performance("RSI_14", was_correct=False)
        self.registry.update_performance("RSI_14", was_correct=True)
        spec = self.registry.get("RSI_14")
        assert spec is not None
        assert spec.signal_count == 3
        assert spec.correct_count == 2
        assert spec.reliability == pytest.approx(2 / 3)

    def test_update_performance_nonexistent(self):
        # Should do nothing and not raise
        self.registry.update_performance("NONEXIST", was_correct=True)

    def test_get_reliability_after_updates(self):
        self.registry.update_performance("MACD_12_26_9", was_correct=True)
        self.registry.update_performance("MACD_12_26_9", was_correct=True)
        self.registry.update_performance("MACD_12_26_9", was_correct=False)
        assert self.registry.get_reliability("MACD_12_26_9") == pytest.approx(2 / 3)


class TestGetWeight:
    def setup_method(self):
        self.registry = IndicatorRegistry()

    def test_get_weight_default(self):
        assert self.registry.get_weight("RSI_14") == pytest.approx(1.0)

    def test_get_weight_missing(self):
        assert self.registry.get_weight("NONEXIST") == pytest.approx(1.0)

    def test_update_weight(self):
        self.registry.update_weight("RSI_14", 2.5)
        assert self.registry.get_weight("RSI_14") == pytest.approx(2.5)

    def test_update_weight_clamp_low(self):
        self.registry.update_weight("RSI_14", 0.01)
        assert self.registry.get_weight("RSI_14") == pytest.approx(0.1)

    def test_update_weight_clamp_high(self):
        self.registry.update_weight("RSI_14", 5.0)
        assert self.registry.get_weight("RSI_14") == pytest.approx(3.0)

    def test_update_weight_boundary_low(self):
        self.registry.update_weight("RSI_14", 0.1)
        assert self.registry.get_weight("RSI_14") == pytest.approx(0.1)

    def test_update_weight_boundary_high(self):
        self.registry.update_weight("RSI_14", 3.0)
        assert self.registry.get_weight("RSI_14") == pytest.approx(3.0)

    def test_update_weight_nonexistent_no_error(self):
        # Updating a nonexistent indicator should not raise
        self.registry.update_weight("NONEXIST", 2.0)


class TestGetReliability:
    def setup_method(self):
        self.registry = IndicatorRegistry()

    def test_get_reliability_default(self):
        assert self.registry.get_reliability("RSI_14") == pytest.approx(0.5)

    def test_get_reliability_missing(self):
        assert self.registry.get_reliability("NONEXIST") == pytest.approx(0.5)
