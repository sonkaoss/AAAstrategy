"""ISentinelProvider port interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ISentinelProvider(ABC):
    """Port for reading data from the external Sentinel risk service."""

    @abstractmethod
    def get_sentinel_data(self) -> dict[str, Any]: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_risk_score(self) -> int: ...

    @abstractmethod
    def get_strategy_mode(self) -> str: ...

    @abstractmethod
    def get_data_age_seconds(self) -> int: ...
