"""Domain port interfaces (hexagonal architecture — secondary ports)."""
from __future__ import annotations

from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository

__all__ = [
    "IAnalyticsEmitter",
    "IConfigProvider",
    "IDataProvider",
    "IIndicatorEngine",
    "ISentinelProvider",
    "IStorageProvider",
    "ITradeRepository",
]
