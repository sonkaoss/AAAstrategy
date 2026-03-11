"""Dependency Injection Container for Nexus Strategy hexagonal architecture."""
from __future__ import annotations

import logging
from typing import Any, TypeVar

from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository

T = TypeVar("T")

REQUIRED_PORTS: list[type] = [IConfigProvider, IAnalyticsEmitter]
OPTIONAL_PORTS: list[type] = [IDataProvider, IIndicatorEngine, ISentinelProvider, IStorageProvider, ITradeRepository]

logger = logging.getLogger(__name__)


class DependencyContainer:
    """Container for registering and resolving port-adapter bindings."""

    def __init__(self) -> None:
        self._registry: dict[type, Any] = {}

    def register(self, port_type: type, adapter_instance: Any) -> None:
        """Register an adapter instance for a port interface."""
        logger.debug("Registering adapter for port %s", port_type.__name__)
        self._registry[port_type] = adapter_instance

    def resolve(self, port_type: type[T]) -> T:
        """Resolve a port to its registered adapter. Raises KeyError if not found."""
        if port_type not in self._registry:
            raise KeyError(f"No adapter registered for port: {port_type.__name__}")
        return self._registry[port_type]  # type: ignore[return-value]

    def has(self, port_type: type) -> bool:
        """Check if a port has a registered adapter."""
        return port_type in self._registry

    def validate(self) -> None:
        """Validate all REQUIRED_PORTS are registered. Raises ValueError with missing port names."""
        missing = [port.__name__ for port in REQUIRED_PORTS if port not in self._registry]
        if missing:
            raise ValueError(f"DependencyContainer missing required ports: {', '.join(missing)}")
        logger.debug("DependencyContainer validation passed.")
