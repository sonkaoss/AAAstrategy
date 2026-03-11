"""IAnalyticsEmitter port interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IAnalyticsEmitter(ABC):
    """Port for emitting metrics and decision logs to an analytics backend."""

    @abstractmethod
    def emit_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None: ...

    @abstractmethod
    def log_decision(
        self,
        decision_type: str,
        pair: str,
        details: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def log_event(self, event_type: str, data: dict[str, Any]) -> None: ...
