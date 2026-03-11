"""Tests for DependencyContainer (TDD - written before implementation)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository

from nexus_strategy.application.dependency_container import DependencyContainer


class TestDependencyContainerRegisterAndResolve(unittest.TestCase):
    """Register and resolve: register a mock IConfigProvider, resolve returns same instance."""

    def test_register_and_resolve_returns_same_instance(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock_config)
        resolved = container.resolve(IConfigProvider)
        self.assertIs(resolved, mock_config)


class TestDependencyContainerResolveUnregistered(unittest.TestCase):
    """Resolve unregistered raises KeyError."""

    def test_resolve_unregistered_raises_key_error(self):
        container = DependencyContainer()
        with self.assertRaises(KeyError):
            container.resolve(IConfigProvider)


class TestDependencyContainerMultiplePorts(unittest.TestCase):
    """Register multiple ports: register 3 different mocks, resolve each correctly."""

    def test_register_multiple_ports_resolve_correctly(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        mock_analytics = MagicMock(spec=IAnalyticsEmitter)
        mock_data = MagicMock(spec=IDataProvider)

        container.register(IConfigProvider, mock_config)
        container.register(IAnalyticsEmitter, mock_analytics)
        container.register(IDataProvider, mock_data)

        self.assertIs(container.resolve(IConfigProvider), mock_config)
        self.assertIs(container.resolve(IAnalyticsEmitter), mock_analytics)
        self.assertIs(container.resolve(IDataProvider), mock_data)


class TestDependencyContainerRegisterOverwrites(unittest.TestCase):
    """Register overwrites: register same port twice, second wins."""

    def test_register_overwrites_previous_registration(self):
        container = DependencyContainer()
        first_mock = MagicMock(spec=IConfigProvider)
        second_mock = MagicMock(spec=IConfigProvider)

        container.register(IConfigProvider, first_mock)
        container.register(IConfigProvider, second_mock)

        resolved = container.resolve(IConfigProvider)
        self.assertIs(resolved, second_mock)
        self.assertIsNot(resolved, first_mock)


class TestDependencyContainerHas(unittest.TestCase):
    """has: returns False before registration, True after."""

    def test_has_returns_false_before_registration(self):
        container = DependencyContainer()
        self.assertFalse(container.has(IConfigProvider))

    def test_has_returns_true_after_registration(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock_config)
        self.assertTrue(container.has(IConfigProvider))


class TestDependencyContainerValidate(unittest.TestCase):
    """validate: raises ValueError with 'missing' when required ports not registered,
    passes when IConfigProvider + IAnalyticsEmitter are registered."""

    def test_validate_raises_value_error_when_required_ports_missing(self):
        container = DependencyContainer()
        with self.assertRaises(ValueError) as ctx:
            container.validate()
        self.assertIn("missing", str(ctx.exception).lower())

    def test_validate_raises_value_error_when_only_one_required_port_registered(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock_config)
        with self.assertRaises(ValueError) as ctx:
            container.validate()
        self.assertIn("missing", str(ctx.exception).lower())

    def test_validate_passes_when_all_required_ports_registered(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        mock_analytics = MagicMock(spec=IAnalyticsEmitter)
        container.register(IConfigProvider, mock_config)
        container.register(IAnalyticsEmitter, mock_analytics)
        # Should not raise
        container.validate()

    def test_validate_error_message_contains_missing_port_names(self):
        container = DependencyContainer()
        # Only register IConfigProvider, IAnalyticsEmitter is missing
        mock_config = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock_config)
        with self.assertRaises(ValueError) as ctx:
            container.validate()
        error_msg = str(ctx.exception)
        self.assertIn("IAnalyticsEmitter", error_msg)


if __name__ == "__main__":
    unittest.main()
