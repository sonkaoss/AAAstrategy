"""Indicator Registry — tracks all technical indicators used by the Nexus strategy."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndicatorSpec:
    """Specification for a single technical indicator, including adaptive stats."""

    name: str
    category: str  # "momentum", "trend", "volatility", "volume", "statistical"
    timeframes: list[str]
    params: dict[str, Any]
    weight: float = 1.0       # adaptive weight, clamped to [0.1, 3.0]
    reliability: float = 0.5  # 0.0-1.0
    signal_count: int = 0
    correct_count: int = 0


class IndicatorRegistry:
    """Registry of all technical indicators used by the Nexus strategy.

    Maintains metadata, adaptive weights and reliability scores for each
    indicator.  Starts populated with 33 default indicators spanning five
    categories: momentum, trend, volatility, volume and statistical.
    """

    def __init__(self) -> None:
        self._indicators: dict[str, IndicatorSpec] = {}
        self._register_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, spec: IndicatorSpec) -> None:
        """Add or overwrite an indicator spec in the registry."""
        self._indicators[spec.name] = spec

    def get(self, name: str) -> IndicatorSpec | None:
        """Return the spec for *name*, or None if not registered."""
        return self._indicators.get(name)

    def get_by_category(self, category: str) -> list[IndicatorSpec]:
        """Return all specs belonging to *category* (empty list if none)."""
        return [s for s in self._indicators.values() if s.category == category]

    def get_all(self) -> list[IndicatorSpec]:
        """Return all registered indicator specs."""
        return list(self._indicators.values())

    def update_performance(self, name: str, was_correct: bool) -> None:
        """Record one signal outcome for *name*.

        Increments ``signal_count`` unconditionally; increments
        ``correct_count`` only when *was_correct* is True; recomputes
        ``reliability`` as the running accuracy ratio.  Does nothing
        when *name* is not registered.
        """
        spec = self._indicators.get(name)
        if spec is None:
            return
        spec.signal_count += 1
        if was_correct:
            spec.correct_count += 1
        spec.reliability = spec.correct_count / spec.signal_count

    def get_weight(self, name: str) -> float:
        """Return the adaptive weight for *name*, defaulting to 1.0."""
        spec = self._indicators.get(name)
        if spec is None:
            return 1.0
        return spec.weight

    def update_weight(self, name: str, new_weight: float) -> None:
        """Set the weight for *name*, clamping to [0.1, 3.0].

        Does nothing when *name* is not registered.
        """
        spec = self._indicators.get(name)
        if spec is None:
            return
        spec.weight = max(0.1, min(3.0, new_weight))

    def get_reliability(self, name: str) -> float:
        """Return the reliability score for *name*, defaulting to 0.5."""
        spec = self._indicators.get(name)
        if spec is None:
            return 0.5
        return spec.reliability

    # ------------------------------------------------------------------
    # Default indicators
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:  # noqa: PLR0915  (many statements, intentional)
        """Populate the registry with the 33 canonical Nexus indicators."""

        _m = "momentum"
        _t = "trend"
        _v = "volatility"
        _vol = "volume"
        _s = "statistical"

        defaults: list[IndicatorSpec] = [
            # ---- Momentum (7) ----
            IndicatorSpec("RSI_14",      _m, ["5m", "15m", "1h", "4h"],   {"period": 14}),
            IndicatorSpec("RSI_7",       _m, ["5m"],                       {"period": 7}),
            IndicatorSpec("StochRSI_K",  _m, ["5m", "15m", "1h"],         {"period": 14, "smooth_k": 3}),
            IndicatorSpec("StochRSI_D",  _m, ["5m", "15m", "1h"],         {"period": 14, "smooth_d": 3}),
            IndicatorSpec("MFI_14",      _m, ["5m", "1h"],                 {"period": 14}),
            IndicatorSpec("CCI_20",      _m, ["5m", "1h"],                 {"period": 20}),
            IndicatorSpec("ROC_9",       _m, ["5m", "15m"],                {"period": 9}),

            # ---- Trend (10) ----
            IndicatorSpec("EMA_9",          _t, ["5m", "15m"],             {"period": 9}),
            IndicatorSpec("EMA_21",         _t, ["5m", "15m"],             {"period": 21}),
            IndicatorSpec("EMA_50",         _t, ["5m", "1h", "4h"],        {"period": 50}),
            IndicatorSpec("EMA_200",        _t, ["5m", "1h", "4h", "1d"], {"period": 200}),
            IndicatorSpec("SMA_20",         _t, ["5m"],                    {"period": 20}),
            IndicatorSpec("SMA_50",         _t, ["1h", "4h"],              {"period": 50}),
            IndicatorSpec("MACD_12_26_9",   _t, ["5m", "1h", "4h"],       {"fast": 12, "slow": 26, "signal": 9}),
            IndicatorSpec("MACD_signal",    _t, ["5m", "1h", "4h"],       {"fast": 12, "slow": 26, "signal": 9}),
            IndicatorSpec("MACD_hist",      _t, ["5m", "1h", "4h"],       {"fast": 12, "slow": 26, "signal": 9}),
            IndicatorSpec("ADX_14",         _t, ["5m", "1h", "4h"],        {"period": 14}),

            # ---- Volatility (9) ----
            IndicatorSpec("DI_plus_14",   _v, ["5m", "1h"],               {"period": 14}),
            IndicatorSpec("DI_minus_14",  _v, ["5m", "1h"],               {"period": 14}),
            IndicatorSpec("BB_upper_20",  _v, ["5m", "1h"],               {"period": 20, "std": 2.0}),
            IndicatorSpec("BB_mid_20",    _v, ["5m", "1h"],               {"period": 20, "std": 2.0}),
            IndicatorSpec("BB_lower_20",  _v, ["5m", "1h"],               {"period": 20, "std": 2.0}),
            IndicatorSpec("BB_width_20",  _v, ["5m", "1h"],               {"period": 20, "std": 2.0}),
            IndicatorSpec("ATR_14",       _v, ["5m", "1h", "4h"],         {"period": 14}),
            IndicatorSpec("Keltner_upper", _v, ["5m"],                    {"period": 20, "multiplier": 1.5}),
            IndicatorSpec("Keltner_lower", _v, ["5m"],                    {"period": 20, "multiplier": 1.5}),

            # ---- Volume (3) ----
            IndicatorSpec("OBV",          _vol, ["5m", "1h"],             {}),
            IndicatorSpec("CMF_20",       _vol, ["5m", "1h"],             {"period": 20}),
            IndicatorSpec("Volume_SMA_20", _vol, ["5m"],                  {"period": 20}),

            # ---- Statistical (2) ----
            IndicatorSpec("Hurst_50",      _s, ["1h", "4h"],              {"period": 50}),
            IndicatorSpec("Parkinson_Vol", _s, ["5m", "1h"],              {"period": 20}),

            # ---- Trend extras (2) ----
            IndicatorSpec("Supertrend_10_3", _t, ["5m", "1h"],            {"period": 10, "multiplier": 3.0}),
            IndicatorSpec("WilliamsR_14",    _t, ["5m"],                   {"period": 14}),
        ]

        for spec in defaults:
            self._indicators[spec.name] = spec
