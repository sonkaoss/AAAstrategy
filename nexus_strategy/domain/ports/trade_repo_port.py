"""ITradeRepository port interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from nexus_strategy.domain.models.trade_context import TradeContext


class ITradeRepository(ABC):
    """Port for persisting and retrieving TradeContext objects."""

    @abstractmethod
    def save_context(self, trade_id: str, context: TradeContext) -> None: ...

    @abstractmethod
    def load_context(self, trade_id: str) -> TradeContext | None: ...

    @abstractmethod
    def delete_context(self, trade_id: str) -> None: ...

    @abstractmethod
    def list_active_contexts(self) -> list[TradeContext]: ...
