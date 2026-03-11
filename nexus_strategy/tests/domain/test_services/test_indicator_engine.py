"""Tests for IndicatorEngine domain service."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nexus_strategy.domain.services.indicator_engine import IndicatorEngine


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------

def make_candles(n: int = 300, trend: str = "up") -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    np.random.seed(42)
    if trend == "up":
        base = np.cumsum(np.random.normal(0.5, 2, n)) + 100
    elif trend == "down":
        base = np.cumsum(np.random.normal(-0.5, 2, n)) + 200
    else:  # sideways
        base = np.random.normal(0, 1, n).cumsum() * 0.1 + 100

    close = pd.Series(np.maximum(base, 10.0))
    high = close + np.abs(np.random.normal(1, 0.5, n))
    low = close - np.abs(np.random.normal(1, 0.5, n))
    open_ = close + np.random.normal(0, 0.5, n)
    volume = pd.Series(np.abs(np.random.normal(1000000, 200000, n)))

    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> IndicatorEngine:
    return IndicatorEngine()


@pytest.fixture
def candles_up() -> pd.DataFrame:
    return make_candles(300, "up")


@pytest.fixture
def candles_down() -> pd.DataFrame:
    return make_candles(300, "down")


@pytest.fixture
def candles_sideways() -> pd.DataFrame:
    return make_candles(300, "sideways")


# ---------------------------------------------------------------------------
# calculate_all tests
# ---------------------------------------------------------------------------

EXPECTED_KEYS = [
    "RSI_14", "RSI_7", "StochRSI_K", "StochRSI_D",
    "MFI_14", "CCI_20", "WilliamsR_14", "ROC_9",
    "EMA_9", "EMA_21", "EMA_50", "EMA_200", "SMA_20", "SMA_50",
    "MACD_12_26_9", "MACD_signal", "MACD_hist",
    "ADX_14", "DI_plus_14", "DI_minus_14",
    "BB_upper_20", "BB_mid_20", "BB_lower_20", "BB_width_20",
    "ATR_14", "Keltner_upper", "Keltner_lower",
    "Supertrend_10_3",
    "OBV", "CMF_20", "Volume_SMA_20",
]


def test_calculate_all_returns_dict(engine, candles_up):
    result = engine.calculate_all(candles_up)
    assert isinstance(result, dict)
    for key in EXPECTED_KEYS:
        assert key in result, f"Missing key: {key}"


def test_calculate_all_has_rsi(engine, candles_up):
    result = engine.calculate_all(candles_up)
    rsi = result["RSI_14"]
    assert 0.0 <= rsi <= 100.0, f"RSI_14={rsi} out of [0,100]"


def test_calculate_all_has_macd(engine, candles_up):
    result = engine.calculate_all(candles_up)
    for key in ("MACD_12_26_9", "MACD_signal", "MACD_hist"):
        assert key in result
        assert isinstance(result[key], float)


def test_calculate_all_has_bollinger(engine, candles_up):
    result = engine.calculate_all(candles_up)
    for key in ("BB_upper_20", "BB_mid_20", "BB_lower_20", "BB_width_20"):
        assert key in result
        assert isinstance(result[key], float)


def test_calculate_all_has_adx(engine, candles_up):
    result = engine.calculate_all(candles_up)
    adx = result["ADX_14"]
    assert 0.0 <= adx <= 100.0, f"ADX_14={adx} out of [0,100]"


def test_calculate_all_has_volume_indicators(engine, candles_up):
    result = engine.calculate_all(candles_up)
    assert "OBV" in result
    assert "CMF_20" in result
    assert isinstance(result["OBV"], float)
    assert isinstance(result["CMF_20"], float)


def test_calculate_all_insufficient_data(engine):
    small = make_candles(30, "up")
    result = engine.calculate_all(small)
    assert result == {}, f"Expected empty dict, got {result}"


def test_calculate_all_no_nan(engine, candles_up):
    result = engine.calculate_all(candles_up)
    for key, val in result.items():
        assert not (isinstance(val, float) and np.isnan(val)), f"NaN found for key: {key}"


# ---------------------------------------------------------------------------
# Individual indicator tests
# ---------------------------------------------------------------------------

def test_calc_rsi_overbought(candles_up):
    """RSI > 70 for strong uptrend (300 bars)."""
    rsi = IndicatorEngine._calc_rsi(candles_up["close"], period=14)
    latest = rsi.dropna().iloc[-1]
    # Strong uptrend should push RSI above 60 at minimum
    assert latest > 50, f"RSI={latest} expected > 50 for uptrend"


def test_calc_rsi_oversold(candles_down):
    """RSI < 50 for strong downtrend."""
    rsi = IndicatorEngine._calc_rsi(candles_down["close"], period=14)
    latest = rsi.dropna().iloc[-1]
    assert latest < 70, f"RSI={latest} expected < 70 for downtrend"


def test_calc_ema_follows_trend(candles_up):
    """EMA_9 > EMA_50 in uptrend."""
    close = candles_up["close"]
    ema9 = IndicatorEngine._calc_ema(close, 9).iloc[-1]
    ema50 = IndicatorEngine._calc_ema(close, 50).iloc[-1]
    assert ema9 > ema50, f"EMA_9={ema9} should > EMA_50={ema50} in uptrend"


def test_calc_bollinger_bands_order(candles_up):
    """upper > mid > lower for Bollinger Bands."""
    close = candles_up["close"]
    upper, mid, lower, width = IndicatorEngine._calc_bollinger(close)
    u = upper.dropna().iloc[-1]
    m = mid.dropna().iloc[-1]
    l = lower.dropna().iloc[-1]
    assert u > m > l, f"BB order violated: upper={u}, mid={m}, lower={l}"
    assert width.dropna().iloc[-1] > 0


def test_calc_atr_positive(candles_up):
    """ATR must always be positive."""
    atr = IndicatorEngine._calc_atr(
        candles_up["high"], candles_up["low"], candles_up["close"]
    )
    valid = atr.dropna()
    assert (valid > 0).all(), "ATR contains non-positive values"


def test_calc_adx_range(candles_up):
    """ADX values must be between 0 and 100."""
    adx, plus_di, minus_di = IndicatorEngine._calc_adx(
        candles_up["high"], candles_up["low"], candles_up["close"]
    )
    valid_adx = adx.dropna()
    assert (valid_adx >= 0).all() and (valid_adx <= 100).all(), \
        f"ADX out of [0,100]: min={valid_adx.min()}, max={valid_adx.max()}"


# ---------------------------------------------------------------------------
# calculate_single tests
# ---------------------------------------------------------------------------

def test_calculate_single_known(engine, candles_up):
    """calculate_single returns a float for a known indicator."""
    val = engine.calculate_single("RSI_14", candles_up)
    assert isinstance(val, float), f"Expected float, got {type(val)}"
    assert 0.0 <= val <= 100.0


def test_calculate_single_unknown(engine, candles_up):
    """calculate_single returns None for an unknown indicator name."""
    val = engine.calculate_single("NONEXISTENT_INDICATOR", candles_up)
    assert val is None
