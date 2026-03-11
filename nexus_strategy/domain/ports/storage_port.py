"""IStorageProvider port interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStorageProvider(ABC):
    """Port for persisting and loading arbitrary documents and time-series data."""

    @abstractmethod
    def save(self, collection: str, data: dict[str, Any]) -> None: ...

    @abstractmethod
    def load(
        self,
        collection: str,
        query: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def save_time_series(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None: ...
