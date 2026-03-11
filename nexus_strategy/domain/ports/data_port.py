"""IDataProvider and IIndicatorEngine port interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from nexus_strategy.domain.models.market_state import MarketState


class IDataProvider(ABC):
    """Port for fetching raw market data."""

    @abstractmethod
    def get_market_state(self, pair: str, timeframe: str) -> MarketState: ...

    @abstractmethod
    def get_candles(self, pair: str, timeframe: str, count: int) -> dict[str, np.ndarray]: ...

    @abstractmethod
    def get_available_pairs(self) -> list[str]: ...


class IIndicatorEngine(ABC):
    """Port for calculating and retrieving technical indicators."""

    @abstractmethod
    def calculate(self, pair: str, timeframe: str, candles: dict[str, np.ndarray]) -> dict[str, float]: ...

    @abstractmethod
    def get_indicator(self, pair: str, timeframe: str, indicator_name: str) -> float | None: ...
