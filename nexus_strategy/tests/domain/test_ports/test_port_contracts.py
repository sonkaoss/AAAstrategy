"""Tests that all port interfaces are valid ABCs and cannot be instantiated."""
from __future__ import annotations

import pytest
from abc import ABC

from nexus_strategy.domain.ports import (
    IAnalyticsEmitter,
    IConfigProvider,
    IDataProvider,
    IIndicatorEngine,
    ISentinelProvider,
    IStorageProvider,
    ITradeRepository,
)

ALL_PORTS = [
    IDataProvider,
    IIndicatorEngine,
    ISentinelProvider,
    IConfigProvider,
    IStorageProvider,
    IAnalyticsEmitter,
    ITradeRepository,
]


# ---------------------------------------------------------------------------
# ABC subclass checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port_cls", ALL_PORTS, ids=lambda c: c.__name__)
def test_port_is_abc_subclass(port_cls):
    """Every port class must be a subclass of ABC."""
    assert issubclass(port_cls, ABC), f"{port_cls.__name__} is not an ABC subclass"


# ---------------------------------------------------------------------------
# Non-instantiability checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port_cls", ALL_PORTS, ids=lambda c: c.__name__)
def test_port_cannot_be_instantiated(port_cls):
    """Directly instantiating any port class must raise TypeError."""
    with pytest.raises(TypeError):
        port_cls()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Abstract method presence checks
# ---------------------------------------------------------------------------

def test_idata_provider_abstract_methods():
    expected = {"get_market_state", "get_candles", "get_available_pairs"}
    assert expected <= IDataProvider.__abstractmethods__


def test_iindicator_engine_abstract_methods():
    expected = {"calculate", "get_indicator"}
    assert expected <= IIndicatorEngine.__abstractmethods__


def test_isentinel_provider_abstract_methods():
    expected = {
        "get_sentinel_data",
        "is_connected",
        "get_risk_score",
        "get_strategy_mode",
        "get_data_age_seconds",
    }
    assert expected <= ISentinelProvider.__abstractmethods__


def test_iconfig_provider_abstract_methods():
    expected = {
        "get",
        "get_profile",
        "get_strategy_config",
        "get_regime_weights",
        "on_config_change",
    }
    assert expected <= IConfigProvider.__abstractmethods__


def test_istorage_provider_abstract_methods():
    expected = {"save", "load", "save_time_series"}
    assert expected <= IStorageProvider.__abstractmethods__


def test_ianalytics_emitter_abstract_methods():
    expected = {"emit_metric", "log_decision", "log_event"}
    assert expected <= IAnalyticsEmitter.__abstractmethods__


def test_itrade_repository_abstract_methods():
    expected = {
        "save_context",
        "load_context",
        "delete_context",
        "list_active_contexts",
    }
    assert expected <= ITradeRepository.__abstractmethods__


# ---------------------------------------------------------------------------
# hasattr convenience checks (public API surface)
# ---------------------------------------------------------------------------

def test_idata_provider_has_expected_attrs():
    for name in ("get_market_state", "get_candles", "get_available_pairs"):
        assert hasattr(IDataProvider, name), f"IDataProvider missing {name}"


def test_iindicator_engine_has_expected_attrs():
    for name in ("calculate", "get_indicator"):
        assert hasattr(IIndicatorEngine, name), f"IIndicatorEngine missing {name}"


def test_isentinel_provider_has_expected_attrs():
    for name in (
        "get_sentinel_data",
        "is_connected",
        "get_risk_score",
        "get_strategy_mode",
        "get_data_age_seconds",
    ):
        assert hasattr(ISentinelProvider, name), f"ISentinelProvider missing {name}"


def test_iconfig_provider_has_expected_attrs():
    for name in (
        "get",
        "get_profile",
        "get_strategy_config",
        "get_regime_weights",
        "on_config_change",
    ):
        assert hasattr(IConfigProvider, name), f"IConfigProvider missing {name}"


def test_istorage_provider_has_expected_attrs():
    for name in ("save", "load", "save_time_series"):
        assert hasattr(IStorageProvider, name), f"IStorageProvider missing {name}"


def test_ianalytics_emitter_has_expected_attrs():
    for name in ("emit_metric", "log_decision", "log_event"):
        assert hasattr(IAnalyticsEmitter, name), f"IAnalyticsEmitter missing {name}"


def test_itrade_repository_has_expected_attrs():
    for name in (
        "save_context",
        "load_context",
        "delete_context",
        "list_active_contexts",
    ):
        assert hasattr(ITradeRepository, name), f"ITradeRepository missing {name}"
