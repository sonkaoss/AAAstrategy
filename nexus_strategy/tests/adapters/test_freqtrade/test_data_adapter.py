"""Tests for FreqtradeDataAdapter."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from nexus_strategy.adapters.freqtrade.data_adapter import FreqtradeDataAdapter
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.ports.config_port import IConfigProvider


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(rows: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(rows) * 0.5)
    return pd.DataFrame({
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.random.randint(100, 1000, rows).astype(float),
        "date": pd.date_range("2024-01-01", periods=rows, freq="5min"),
    })


def _make_config() -> IConfigProvider:
    """Return a mock IConfigProvider."""
    return MagicMock(spec=IConfigProvider)


def _make_adapter() -> FreqtradeDataAdapter:
    return FreqtradeDataAdapter(config=_make_config())


# ---------------------------------------------------------------------------
# set_dataframes
# ---------------------------------------------------------------------------

class TestSetDataframes:
    def test_stores_dataframes(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter._dataframes["BTC/USDT"]["5m"]
        assert result is df

    def test_updates_available_pairs(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({
            "BTC/USDT": {"5m": df},
            "ETH/USDT": {"5m": df},
        })
        pairs = adapter.get_available_pairs()
        assert "BTC/USDT" in pairs
        assert "ETH/USDT" in pairs
        assert len(pairs) == 2

    def test_overwrites_previous_data(self):
        adapter = _make_adapter()
        df1 = _make_ohlcv(50)
        df2 = _make_ohlcv(80)
        adapter.set_dataframes({"BTC/USDT": {"5m": df1}})
        adapter.set_dataframes({"ETH/USDT": {"5m": df2}})
        # BTC/USDT should no longer be present
        assert "BTC/USDT" not in adapter.get_available_pairs()
        assert "ETH/USDT" in adapter.get_available_pairs()

    def test_empty_dict_clears_pairs(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        adapter.set_dataframes({})
        assert adapter.get_available_pairs() == []


# ---------------------------------------------------------------------------
# get_available_pairs
# ---------------------------------------------------------------------------

class TestGetAvailablePairs:
    def test_empty_before_set_dataframes(self):
        adapter = _make_adapter()
        assert adapter.get_available_pairs() == []

    def test_returns_list(self):
        adapter = _make_adapter()
        assert isinstance(adapter.get_available_pairs(), list)

    def test_returns_copy(self):
        """Mutating the returned list must not affect the adapter's state."""
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        pairs = adapter.get_available_pairs()
        pairs.append("FAKE/USDT")
        assert "FAKE/USDT" not in adapter.get_available_pairs()

    def test_multiple_pairs(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({
            "BTC/USDT": {"5m": df},
            "ETH/USDT": {"5m": df},
            "SOL/USDT": {"5m": df},
        })
        assert sorted(adapter.get_available_pairs()) == [
            "BTC/USDT", "ETH/USDT", "SOL/USDT"
        ]


# ---------------------------------------------------------------------------
# get_market_state — happy path
# ---------------------------------------------------------------------------

class TestGetMarketStateHappyPath:
    def test_returns_market_state_instance(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        assert isinstance(result, MarketState)

    def test_pair_and_timeframe_in_indicators(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        assert "BTC/USDT" in result.indicators
        assert "5m" in result.indicators["BTC/USDT"]

    def test_ohlcv_values_match_last_row(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        last = df.iloc[-1]
        ind = result.indicators["BTC/USDT"]["5m"]
        assert ind["open"] == pytest.approx(float(last["open"]))
        assert ind["high"] == pytest.approx(float(last["high"]))
        assert ind["low"] == pytest.approx(float(last["low"]))
        assert ind["close"] == pytest.approx(float(last["close"]))
        assert ind["volume"] == pytest.approx(float(last["volume"]))

    def test_timestamp_extracted_from_date_column(self):
        adapter = _make_adapter()
        df = _make_ohlcv(10)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        expected = pd.Timestamp(df.iloc[-1]["date"]).to_pydatetime()
        assert result.timestamp == expected

    def test_market_state_is_frozen(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        with pytest.raises((AttributeError, TypeError)):
            result.btc_price = 99999.0  # type: ignore


# ---------------------------------------------------------------------------
# get_market_state — missing pair / timeframe
# ---------------------------------------------------------------------------

class TestGetMarketStateMissing:
    def test_missing_pair_returns_market_state(self):
        adapter = _make_adapter()
        result = adapter.get_market_state("MISSING/USDT", "5m")
        assert isinstance(result, MarketState)

    def test_missing_pair_has_empty_ohlcv(self):
        adapter = _make_adapter()
        result = adapter.get_market_state("MISSING/USDT", "5m")
        # The pair should be present but its indicator dict should be empty
        inner = result.indicators.get("MISSING/USDT", {}).get("5m", {})
        assert inner == {}

    def test_missing_timeframe_returns_empty_ohlcv(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_market_state("BTC/USDT", "1h")
        inner = result.indicators.get("BTC/USDT", {}).get("1h", {})
        assert inner == {}

    def test_missing_pair_timestamp_is_datetime(self):
        adapter = _make_adapter()
        result = adapter.get_market_state("MISSING/USDT", "5m")
        assert isinstance(result.timestamp, datetime)

    def test_no_dataframes_set(self):
        adapter = _make_adapter()
        result = adapter.get_market_state("BTC/USDT", "5m")
        assert isinstance(result, MarketState)


# ---------------------------------------------------------------------------
# get_market_state — empty DataFrame
# ---------------------------------------------------------------------------

class TestGetMarketStateEmptyDataFrame:
    def test_empty_df_returns_market_state(self):
        adapter = _make_adapter()
        empty_df = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume", "date"]
        )
        adapter.set_dataframes({"BTC/USDT": {"5m": empty_df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        assert isinstance(result, MarketState)

    def test_empty_df_has_empty_ohlcv(self):
        adapter = _make_adapter()
        empty_df = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume", "date"]
        )
        adapter.set_dataframes({"BTC/USDT": {"5m": empty_df}})
        result = adapter.get_market_state("BTC/USDT", "5m")
        inner = result.indicators.get("BTC/USDT", {}).get("5m", {})
        assert inner == {}


# ---------------------------------------------------------------------------
# get_candles — happy path
# ---------------------------------------------------------------------------

class TestGetCandlesHappyPath:
    def test_returns_dict_with_ohlcv_keys(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 10)
        assert set(result.keys()) == {"open", "high", "low", "close", "volume"}

    def test_returns_numpy_arrays(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 10)
        for key in result:
            assert isinstance(result[key], np.ndarray), f"{key} is not ndarray"

    def test_count_limits_rows(self):
        adapter = _make_adapter()
        df = _make_ohlcv(100)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 20)
        for key in result:
            assert len(result[key]) == 20

    def test_full_count_returns_all_rows(self):
        adapter = _make_adapter()
        df = _make_ohlcv(50)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 50)
        for key in result:
            assert len(result[key]) == 50

    def test_count_larger_than_data_returns_all(self):
        adapter = _make_adapter()
        df = _make_ohlcv(30)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 1000)
        for key in result:
            assert len(result[key]) == 30

    def test_values_are_last_n_rows(self):
        """The returned arrays must correspond to the last *count* rows of the DF."""
        adapter = _make_adapter()
        df = _make_ohlcv(100)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        count = 15
        result = adapter.get_candles("BTC/USDT", "5m", count)
        expected_close = df["close"].tail(count).to_numpy()
        np.testing.assert_array_almost_equal(result["close"], expected_close)

    def test_count_one(self):
        adapter = _make_adapter()
        df = _make_ohlcv(10)
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "5m", 1)
        for key in result:
            assert len(result[key]) == 1
        assert result["close"][0] == pytest.approx(float(df.iloc[-1]["close"]))


# ---------------------------------------------------------------------------
# get_candles — missing pair / timeframe
# ---------------------------------------------------------------------------

class TestGetCandlesMissing:
    def test_missing_pair_returns_empty_arrays(self):
        adapter = _make_adapter()
        result = adapter.get_candles("MISSING/USDT", "5m", 10)
        assert set(result.keys()) == {"open", "high", "low", "close", "volume"}
        for key in result:
            assert len(result[key]) == 0

    def test_missing_timeframe_returns_empty_arrays(self):
        adapter = _make_adapter()
        df = _make_ohlcv()
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        result = adapter.get_candles("BTC/USDT", "1h", 10)
        for key in result:
            assert len(result[key]) == 0

    def test_no_dataframes_set_returns_empty(self):
        adapter = _make_adapter()
        result = adapter.get_candles("BTC/USDT", "5m", 10)
        for key in result:
            assert isinstance(result[key], np.ndarray)
            assert len(result[key]) == 0


# ---------------------------------------------------------------------------
# get_candles — empty DataFrame
# ---------------------------------------------------------------------------

class TestGetCandlesEmptyDataFrame:
    def test_empty_df_returns_empty_arrays(self):
        adapter = _make_adapter()
        empty_df = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume", "date"]
        )
        adapter.set_dataframes({"BTC/USDT": {"5m": empty_df}})
        result = adapter.get_candles("BTC/USDT", "5m", 10)
        for key in result:
            assert len(result[key]) == 0


# ---------------------------------------------------------------------------
# Edge cases — DataFrame with missing OHLCV columns
# ---------------------------------------------------------------------------

class TestMissingColumns:
    def test_get_market_state_missing_volume_column(self):
        """A DataFrame without a 'volume' column should not crash."""
        adapter = _make_adapter()
        df = _make_ohlcv().drop(columns=["volume"])
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        # Should raise KeyError when slicing missing column in get_candles,
        # but get_market_state uses .get() and therefore must not raise.
        result = adapter.get_market_state("BTC/USDT", "5m")
        assert isinstance(result, MarketState)
        ind = result.indicators["BTC/USDT"]["5m"]
        # volume should default to 0.0 when column is absent
        assert ind.get("volume", 0.0) == pytest.approx(0.0)

    def test_get_market_state_no_date_column_uses_utcnow(self):
        """Without a 'date' column the timestamp should fall back to utcnow."""
        adapter = _make_adapter()
        df = _make_ohlcv().drop(columns=["date"])
        adapter.set_dataframes({"BTC/USDT": {"5m": df}})
        before = datetime.now(timezone.utc)
        result = adapter.get_market_state("BTC/USDT", "5m")
        after = datetime.now(timezone.utc)
        assert before <= result.timestamp <= after


# ---------------------------------------------------------------------------
# Multiple pairs / timeframes
# ---------------------------------------------------------------------------

class TestMultiplePairsTimeframes:
    def test_independent_pairs(self):
        adapter = _make_adapter()
        df_btc = _make_ohlcv(50)
        df_eth = _make_ohlcv(60)
        adapter.set_dataframes({
            "BTC/USDT": {"5m": df_btc},
            "ETH/USDT": {"5m": df_eth},
        })
        candles_btc = adapter.get_candles("BTC/USDT", "5m", 50)
        candles_eth = adapter.get_candles("ETH/USDT", "5m", 60)
        assert len(candles_btc["close"]) == 50
        assert len(candles_eth["close"]) == 60

    def test_multiple_timeframes_same_pair(self):
        adapter = _make_adapter()
        df_5m = _make_ohlcv(100)
        df_1h = _make_ohlcv(50)
        adapter.set_dataframes({
            "BTC/USDT": {
                "5m": df_5m,
                "1h": df_1h,
            }
        })
        ms_5m = adapter.get_market_state("BTC/USDT", "5m")
        ms_1h = adapter.get_market_state("BTC/USDT", "1h")
        ind_5m = ms_5m.indicators["BTC/USDT"]["5m"]
        ind_1h = ms_1h.indicators["BTC/USDT"]["1h"]
        assert ind_5m["close"] == pytest.approx(float(df_5m.iloc[-1]["close"]))
        assert ind_1h["close"] == pytest.approx(float(df_1h.iloc[-1]["close"]))
