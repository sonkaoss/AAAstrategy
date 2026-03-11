from __future__ import annotations

import numpy as np
import pytest

from nexus_strategy.utils.math_utils import (
    hurst_exponent,
    kelly_criterion,
    normalize_to_range,
    parkinson_volatility,
    rolling_sharpe,
    rolling_sortino,
    z_score,
)


# ---------------------------------------------------------------------------
# hurst_exponent
# ---------------------------------------------------------------------------

class TestHurstExponent:
    def test_trending_series_above_half(self):
        """Strongly trending series should produce H > 0.5."""
        prices = np.cumsum(np.ones(200)) + 100.0  # monotonically rising
        h = hurst_exponent(prices)
        assert h > 0.5

    def test_mean_reverting_series_below_half(self):
        """Alternating series should produce H < 0.5."""
        prices = np.array([100.0 + ((-1) ** i) * 0.5 for i in range(200)])
        h = hurst_exponent(prices)
        assert h < 0.5

    def test_short_series_returns_half(self):
        """Series shorter than max_lag*2 should return 0.5."""
        prices = np.arange(10, dtype=float)
        h = hurst_exponent(prices, max_lag=20)
        assert h == 0.5

    def test_output_clipped_to_unit_interval(self):
        prices = np.random.default_rng(42).normal(0, 1, 300).cumsum() + 100
        h = hurst_exponent(prices)
        assert 0.0 <= h <= 1.0


# ---------------------------------------------------------------------------
# rolling_sharpe
# ---------------------------------------------------------------------------

class TestRollingSharpe:
    def test_positive_returns_positive_sharpe(self):
        rng = np.random.default_rng(0)
        returns = np.abs(rng.normal(0.01, 0.001, 50))  # all positive, varied
        assert rolling_sharpe(returns) > 0.0

    def test_negative_returns_negative_sharpe(self):
        rng = np.random.default_rng(0)
        returns = -np.abs(rng.normal(0.01, 0.001, 50))  # all negative, varied
        assert rolling_sharpe(returns) < 0.0

    def test_zero_std_returns_zero(self):
        # Identically equal constant returns → ddof=1 std == 0
        returns = np.full(10, 0.005)
        assert rolling_sharpe(returns) == 0.0

    def test_short_series_returns_zero(self):
        assert rolling_sharpe(np.array([0.01])) == 0.0

    def test_annualisation_factor(self):
        """Sharpe should use sqrt(288) annualisation."""
        returns = np.array([0.01, -0.005, 0.02, 0.0, 0.015])
        result = rolling_sharpe(returns)
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        expected = (mean / std) * np.sqrt(288)
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# rolling_sortino
# ---------------------------------------------------------------------------

class TestRollingSortino:
    def test_positive_returns_positive_sortino(self):
        returns = np.array([0.01, 0.02, 0.015, 0.005, 0.03])
        assert rolling_sortino(returns) > 0.0

    def test_negative_returns_negative_sortino(self):
        returns = np.array([-0.01, -0.02, -0.015])
        assert rolling_sortino(returns) < 0.0

    def test_no_downside_returns_large_positive(self):
        """All positive returns → no downside std → should not raise."""
        returns = np.array([0.01, 0.02, 0.03])
        result = rolling_sortino(returns)
        assert result > 0.0

    def test_short_series_returns_zero(self):
        assert rolling_sortino(np.array([0.01])) == 0.0


# ---------------------------------------------------------------------------
# kelly_criterion
# ---------------------------------------------------------------------------

class TestKellyCriterion:
    def test_positive_edge(self):
        k = kelly_criterion(win_rate=0.6, avg_win=0.02, avg_loss=0.01)
        assert k > 0.0

    def test_negative_edge(self):
        k = kelly_criterion(win_rate=0.3, avg_win=0.01, avg_loss=0.05)
        assert k < 0.0

    def test_zero_avg_loss_returns_zero(self):
        assert kelly_criterion(0.6, 0.02, 0.0) == 0.0

    def test_formula_correctness(self):
        """Kelly = W/L - (1-W) where W=win_rate, L=avg_loss/avg_win."""
        win_rate, avg_win, avg_loss = 0.55, 0.03, 0.02
        k = kelly_criterion(win_rate, avg_win, avg_loss)
        b = avg_win / avg_loss
        expected = win_rate - (1 - win_rate) / b
        assert abs(k - expected) < 1e-9


# ---------------------------------------------------------------------------
# z_score
# ---------------------------------------------------------------------------

class TestZScore:
    def test_above_mean_positive(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert z_score(5.0, data) > 0.0

    def test_below_mean_negative(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert z_score(1.0, data) < 0.0

    def test_zero_std_returns_zero(self):
        data = np.full(5, 3.0)
        assert z_score(3.0, data) == 0.0

    def test_short_series_returns_zero(self):
        assert z_score(1.0, np.array([1.0])) == 0.0

    def test_formula_correctness(self):
        data = np.array([2.0, 4.0, 6.0, 8.0])
        val = 6.0
        result = z_score(val, data)
        expected = (val - np.mean(data)) / np.std(data)
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# parkinson_volatility
# ---------------------------------------------------------------------------

class TestParkinsonVolatility:
    def test_basic_positive_result(self):
        highs = np.array([105.0, 110.0, 108.0])
        lows = np.array([100.0, 104.0, 103.0])
        vol = parkinson_volatility(highs, lows)
        assert vol > 0.0

    def test_equal_highs_lows_returns_zero(self):
        prices = np.array([100.0, 100.0, 100.0])
        vol = parkinson_volatility(prices, prices)
        assert vol == 0.0

    def test_larger_range_larger_vol(self):
        highs_narrow = np.array([101.0, 101.0, 101.0])
        lows_narrow = np.array([99.0, 99.0, 99.0])
        highs_wide = np.array([110.0, 110.0, 110.0])
        lows_wide = np.array([90.0, 90.0, 90.0])
        assert parkinson_volatility(highs_wide, lows_wide) > parkinson_volatility(highs_narrow, lows_narrow)


# ---------------------------------------------------------------------------
# normalize_to_range
# ---------------------------------------------------------------------------

class TestNormalizeToRange:
    def test_basic_normalization(self):
        result = normalize_to_range(5.0, 0.0, 10.0, 0.0, 1.0)
        assert abs(result - 0.5) < 1e-9

    def test_clamp_above_max(self):
        result = normalize_to_range(15.0, 0.0, 10.0, 0.0, 1.0)
        assert result == 1.0

    def test_clamp_below_min(self):
        result = normalize_to_range(-5.0, 0.0, 10.0, 0.0, 1.0)
        assert result == 0.0

    def test_same_in_range_returns_midpoint(self):
        result = normalize_to_range(5.0, 3.0, 3.0, 0.0, 1.0)
        assert result == 0.5

    def test_custom_out_range(self):
        result = normalize_to_range(5.0, 0.0, 10.0, -1.0, 1.0)
        assert abs(result - 0.0) < 1e-9
