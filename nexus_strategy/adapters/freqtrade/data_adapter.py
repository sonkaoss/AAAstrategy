"""FreqtradeDataAdapter — IDataProvider adapter for Freqtrade market data."""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any

from nexus_strategy.domain.ports.data_port import IDataProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import CompositeRegime


class FreqtradeDataAdapter(IDataProvider):
    """Adapter that wraps Freqtrade's injected DataFrames and exposes them
    through the IDataProvider port.

    Lifecycle:
        1. Instantiated with an IConfigProvider.
        2. ``set_dataframes`` is called by the Freqtrade strategy entry-point
           (nexus.py) every time a new batch of candles is available.
        3. Domain services call ``get_market_state`` / ``get_candles`` /
           ``get_available_pairs`` as needed.
    """

    def __init__(self, config: IConfigProvider) -> None:
        self._config = config
        # {pair: {timeframe: DataFrame}}
        self._dataframes: dict[str, dict[str, pd.DataFrame]] = {}
        self._available_pairs: list[str] = []

    # ------------------------------------------------------------------
    # Injection point (called by Freqtrade strategy layer)
    # ------------------------------------------------------------------

    def set_dataframes(
        self, dataframes: dict[str, dict[str, pd.DataFrame]]
    ) -> None:
        """Inject Freqtrade's ``analyzed_dataframe`` mapping.

        Args:
            dataframes: ``{pair: {timeframe: DataFrame}}`` mapping supplied
                by Freqtrade's ``bot_loop_start`` / ``populate_indicators``
                hooks.
        """
        self._dataframes = dataframes
        self._available_pairs = list(dataframes.keys())

    # ------------------------------------------------------------------
    # IDataProvider implementation
    # ------------------------------------------------------------------

    def get_market_state(self, pair: str, timeframe: str) -> MarketState:
        """Build a :class:`MarketState` snapshot from stored DataFrames.

        The ``indicators`` field of the returned ``MarketState`` will contain
        OHLCV values for *this* pair/timeframe only, in the nested structure
        ``{pair: {timeframe: {column: value}}}``.  All macro/sentinel fields
        are set to safe defaults because this adapter does not have access to
        that data.

        Returns a ``MarketState`` with empty indicator dicts when the
        pair/timeframe is not found.
        """
        df = self._dataframes.get(pair, {}).get(timeframe)
        ohlcv: dict[str, float] = {}
        timestamp = datetime.now(timezone.utc)

        if df is not None and not df.empty:
            last = df.iloc[-1]
            ohlcv = {
                "open": float(last.get("open", 0.0)),
                "high": float(last.get("high", 0.0)),
                "low": float(last.get("low", 0.0)),
                "close": float(last.get("close", 0.0)),
                "volume": float(last.get("volume", 0.0)),
            }
            if "date" in df.columns:
                ts = last["date"]
                if isinstance(ts, (pd.Timestamp,)):
                    timestamp = ts.to_pydatetime()
                elif isinstance(ts, datetime):
                    timestamp = ts

        # Nested structure expected by MarketState: {pair: {timeframe: {indicator: value}}}
        indicators: dict[str, dict[str, dict[str, float]]] = {
            pair: {timeframe: ohlcv}
        }

        return MarketState(
            timestamp=timestamp,
            indicators=indicators,
            composite_indicators={},
            regime=self._default_regime(timestamp),
            previous_regime=self._default_regime(timestamp),
            regime_just_changed=False,
            sentinel={},
            sentinel_connected=False,
            sentinel_data_age_seconds=0,
            btc_price=0.0,
            btc_change_1h=0.0,
            btc_change_24h=0.0,
            btc_above_ema200=False,
            btc_trend="unknown",
            market_phase="unknown",
            altcoin_season_index=0,
            fear_greed=0,
            indicator_weights={},
            strategy_weights={},
            indicator_reliability={},
        )

    def get_candles(
        self, pair: str, timeframe: str, count: int
    ) -> dict[str, np.ndarray]:
        """Return OHLCV numpy arrays for the most recent *count* candles.

        Keys: ``open``, ``high``, ``low``, ``close``, ``volume``.
        Returns empty arrays when the pair/timeframe is not found or the
        stored DataFrame is empty.
        """
        _empty: dict[str, np.ndarray] = {
            k: np.array([]) for k in ("open", "high", "low", "close", "volume")
        }
        df = self._dataframes.get(pair, {}).get(timeframe)
        if df is None or df.empty:
            return _empty

        sliced = df.tail(count)
        return {
            "open": sliced["open"].to_numpy(),
            "high": sliced["high"].to_numpy(),
            "low": sliced["low"].to_numpy(),
            "close": sliced["close"].to_numpy(),
            "volume": sliced["volume"].to_numpy(),
        }

    def get_available_pairs(self) -> list[str]:
        """Return pairs currently known to the adapter."""
        return list(self._available_pairs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_regime(timestamp: datetime) -> CompositeRegime:
        """Return a neutral placeholder regime used when real regime data is
        not yet available from the Freqtrade data layer."""
        from nexus_strategy.domain.models.regime import (
            MicroRegime,
            MidRegime,
            MacroRegime,
            SynthesizedRegime,
        )

        return CompositeRegime(
            micro=MicroRegime.MICRO_RANGING,
            mid=MidRegime.RANGING_TIGHT,
            macro=MacroRegime.MACRO_UNCERTAIN,
            synthesized=SynthesizedRegime.REGIME_UNCERTAIN,
            confidence=0,
            duration_candles=0,
            transition_probability=0.0,
            recommended_strategies=[],
            risk_multiplier=1.0,
            max_position_size=0.0,
            timestamp=timestamp,
        )
