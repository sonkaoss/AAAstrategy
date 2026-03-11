"""IConfigProvider port interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IConfigProvider(ABC):
    """Port for reading strategy configuration values."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def get_profile(self) -> str: ...

    @abstractmethod
    def get_strategy_config(self, strategy_name: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_regime_weights(self, regime_name: str) -> dict[str, float]: ...

    @abstractmethod
    def on_config_change(self, callback: Any) -> None: ...
