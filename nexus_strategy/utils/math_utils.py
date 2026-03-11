from __future__ import annotations

import numpy as np

# Annualisation factor for 5-minute candles (288 candles per day)
_ANNUALISE = np.sqrt(288)


def hurst_exponent(prices: np.ndarray, max_lag: int = 20) -> float:
    """Compute Hurst exponent via R/S analysis.

    H > 0.5  →  trending
    H < 0.5  →  mean-reverting
    Returns 0.5 when the series is too short (< max_lag * 2).
    Result is clipped to [0, 1].
    """
    prices = np.asarray(prices, dtype=float)
    if len(prices) < max_lag * 2:
        return 0.5

    lags = range(2, max_lag + 1)
    rs_values: list[float] = []
    lag_values: list[int] = []

    for lag in lags:
        # Split series into non-overlapping windows of length `lag`
        n_windows = len(prices) // lag
        if n_windows < 1:
            continue

        rs_list: list[float] = []
        for w in range(n_windows):
            chunk = prices[w * lag: (w + 1) * lag]
            mean = np.mean(chunk)
            deviation = np.cumsum(chunk - mean)
            r = np.max(deviation) - np.min(deviation)
            s = np.std(chunk, ddof=1)
            if s == 0.0:
                continue
            rs_list.append(r / s)

        if rs_list:
            rs_values.append(np.mean(rs_list))
            lag_values.append(lag)

    if len(lag_values) < 2:
        return 0.5

    log_lags = np.log(lag_values)
    log_rs = np.log(rs_values)
    # Linear regression: slope = Hurst exponent
    coeffs = np.polyfit(log_lags, log_rs, 1)
    h = float(coeffs[0])
    return float(np.clip(h, 0.0, 1.0))


def rolling_sharpe(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Annualised Sharpe ratio (sqrt(288) factor for 5-min candles).

    Returns 0 if std == 0 or len < 2.
    """
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free
    std = float(np.std(excess, ddof=1))
    if np.isclose(std, 0.0, atol=1e-12):
        return 0.0
    return float((np.mean(excess) / std) * _ANNUALISE)


def rolling_sortino(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Annualised Sortino ratio (sqrt(288) factor for 5-min candles).

    Uses downside deviation only. Returns 0 if len < 2.
    When there are no downside returns, returns a large positive value
    proportional to mean excess return.
    """
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free
    downside = excess[excess < 0.0]
    if len(downside) == 0:
        # No downside — treat as very high Sortino; use mean * annualise
        mean_exc = float(np.mean(excess))
        return mean_exc * float(_ANNUALISE) * 1e6 if mean_exc != 0.0 else 0.0
    downside_std = np.sqrt(np.mean(downside ** 2))
    if downside_std == 0.0:
        return 0.0
    return float((np.mean(excess) / downside_std) * _ANNUALISE)


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly fraction: W - (1-W)/B where B = avg_win / avg_loss.

    Returns 0 if avg_loss == 0.
    """
    if avg_loss == 0.0:
        return 0.0
    b = avg_win / avg_loss
    return float(win_rate - (1.0 - win_rate) / b)


def z_score(value: float, data: np.ndarray) -> float:
    """Z-score of *value* relative to *data* distribution.

    Returns 0 if std == 0 or len < 2.
    """
    data = np.asarray(data, dtype=float)
    if len(data) < 2:
        return 0.0
    std = np.std(data)
    if std == 0.0:
        return 0.0
    return float((value - np.mean(data)) / std)


def parkinson_volatility(highs: np.ndarray, lows: np.ndarray) -> float:
    """Parkinson volatility estimator using high-low range.

    Returns 0 when highs == lows for all observations.
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    log_hl = np.log(highs / lows)
    # Guard against log(1) == 0 for all entries
    if np.all(log_hl == 0.0):
        return 0.0
    factor = 1.0 / (4.0 * len(highs) * np.log(2.0))
    return float(np.sqrt(factor * np.sum(log_hl ** 2)))


def normalize_to_range(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float = 0.0,
    out_max: float = 1.0,
) -> float:
    """Map *value* from [in_min, in_max] to [out_min, out_max] with clamping.

    Returns midpoint of output range when in_min == in_max.
    """
    if in_min == in_max:
        return (out_min + out_max) / 2.0
    clamped = max(in_min, min(in_max, value))
    ratio = (clamped - in_min) / (in_max - in_min)
    return float(out_min + ratio * (out_max - out_min))
