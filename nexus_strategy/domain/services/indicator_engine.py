"""Indicator Engine — domain service for calculating technical indicators."""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any


class IndicatorEngine:
    """Calculates all technical indicators from OHLCV candle data.

    Domain service — uses numpy/pandas for math (no external TA libs).
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_all(self, candles: pd.DataFrame) -> dict[str, float]:
        """Calculate all indicators for a set of OHLCV candles.

        Args:
            candles: DataFrame with columns: open, high, low, close, volume
                     Must have at least 50 rows for calculation.

        Returns:
            Dict mapping indicator name to latest value.
            Returns empty dict if insufficient data.
        """
        if len(candles) < 50:
            return {}

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        volume = candles["volume"]

        # RSI
        rsi_14 = self._calc_rsi(close, 14)
        rsi_7 = self._calc_rsi(close, 7)

        # StochRSI
        stoch_k, stoch_d = self._calc_stoch_rsi(close)

        # MACD
        macd_line, macd_signal, macd_hist = self._calc_macd(close)

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower, bb_width = self._calc_bollinger(close)

        # ATR
        atr = self._calc_atr(high, low, close)

        # ADX
        adx, plus_di, minus_di = self._calc_adx(high, low, close)

        # MFI
        mfi = self._calc_mfi(high, low, close, volume)

        # OBV
        obv = self._calc_obv(close, volume)

        # CMF
        cmf = self._calc_cmf(high, low, close, volume)

        # Supertrend
        supertrend = self._calc_supertrend(high, low, close)

        # Keltner Channels
        keltner_upper, keltner_lower = self._calc_keltner(high, low, close)

        # Williams %R
        wr = self._calc_williams_r(high, low, close)

        # CCI
        cci = self._calc_cci(high, low, close)

        # ROC
        roc = self._calc_roc(close)

        # EMAs
        ema_9 = self._calc_ema(close, 9)
        ema_21 = self._calc_ema(close, 21)
        ema_50 = self._calc_ema(close, 50)
        ema_200 = self._calc_ema(close, 200)

        # SMAs
        sma_20 = self._calc_sma(close, 20)
        sma_50 = self._calc_sma(close, 50)

        # Volume SMA
        vol_sma_20 = self._calc_sma(volume, 20)

        def _last(series: pd.Series) -> float:
            """Return the last non-NaN value, falling back to 0.0."""
            val = series.iloc[-1]
            if pd.isna(val):
                val = 0.0
            return float(val)

        result: dict[str, float] = {
            "RSI_14": _last(rsi_14),
            "RSI_7": _last(rsi_7),
            "StochRSI_K": _last(stoch_k),
            "StochRSI_D": _last(stoch_d),
            "MFI_14": _last(mfi),
            "CCI_20": _last(cci),
            "WilliamsR_14": _last(wr),
            "ROC_9": _last(roc),
            "EMA_9": _last(ema_9),
            "EMA_21": _last(ema_21),
            "EMA_50": _last(ema_50),
            "EMA_200": _last(ema_200),
            "SMA_20": _last(sma_20),
            "SMA_50": _last(sma_50),
            "MACD_12_26_9": _last(macd_line),
            "MACD_signal": _last(macd_signal),
            "MACD_hist": _last(macd_hist),
            "ADX_14": _last(adx),
            "DI_plus_14": _last(plus_di),
            "DI_minus_14": _last(minus_di),
            "BB_upper_20": _last(bb_upper),
            "BB_mid_20": _last(bb_mid),
            "BB_lower_20": _last(bb_lower),
            "BB_width_20": _last(bb_width),
            "ATR_14": _last(atr),
            "Keltner_upper": _last(keltner_upper),
            "Keltner_lower": _last(keltner_lower),
            "Supertrend_10_3": _last(supertrend),
            "OBV": _last(obv),
            "CMF_20": _last(cmf),
            "Volume_SMA_20": _last(vol_sma_20),
        }

        return result

    def calculate_single(self, name: str, candles: pd.DataFrame) -> float | None:
        """Calculate a single indicator by name.

        Args:
            name: Indicator name (e.g. 'RSI_14', 'MACD_12_26_9').
            candles: OHLCV DataFrame.

        Returns:
            Latest float value, or None if name is unknown.
        """
        result = self.calculate_all(candles)
        if name not in result:
            return None
        return result[name]

    # ------------------------------------------------------------------
    # Private calculation methods
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _calc_sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period).mean()

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index (Wilder's smoothing)."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_stoch_rsi(
        close: pd.Series,
        period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        """Stochastic RSI — K and D lines."""
        rsi = IndicatorEngine._calc_rsi(close, period)
        rsi_min = rsi.rolling(period).min()
        rsi_max = rsi.rolling(period).max()
        stoch = (rsi - rsi_min) / (rsi_max - rsi_min)
        k = stoch.rolling(smooth_k).mean() * 100
        d = k.rolling(smooth_d).mean()
        return k, d

    @staticmethod
    def _calc_macd(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """MACD — line, signal, histogram."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def _calc_bollinger(
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands — upper, mid, lower, width."""
        mid = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = mid + std_dev * std
        lower = mid - std_dev * std
        width = (upper - lower) / mid  # normalized width
        return upper, mid, lower, width

    @staticmethod
    def _calc_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Average True Range."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, min_periods=period).mean()

    @staticmethod
    def _calc_adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """ADX with DI+ and DI-."""
        atr = IndicatorEngine._calc_atr(high, low, close, period)
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=high.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=high.index,
        )
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
        dx = (
            100
            * (plus_di - minus_di).abs()
            / (plus_di + minus_di).replace(0, np.inf)
        )
        adx = dx.ewm(alpha=1 / period, min_periods=period).mean()
        return adx, plus_di, minus_di

    @staticmethod
    def _calc_mfi(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Money Flow Index."""
        typical_price = (high + low + close) / 3
        mf = typical_price * volume
        delta = typical_price.diff()
        pos_mf = (
            pd.Series(np.where(delta > 0, mf, 0.0), index=close.index)
            .rolling(period)
            .sum()
        )
        neg_mf = (
            pd.Series(np.where(delta < 0, mf, 0.0), index=close.index)
            .rolling(period)
            .sum()
        )
        mfi = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.inf)))
        return mfi

    @staticmethod
    def _calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume."""
        direction = np.sign(close.diff())
        return (direction * volume).cumsum()

    @staticmethod
    def _calc_cmf(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int = 20,
    ) -> pd.Series:
        """Chaikin Money Flow."""
        hl_range = high - low
        mfm = pd.Series(
            np.where(
                hl_range != 0,
                ((close - low) - (high - close)) / hl_range,
                0.0,
            ),
            index=close.index,
        )
        mfv = mfm * volume
        return mfv.rolling(period).sum() / volume.rolling(period).sum()

    @staticmethod
    def _calc_supertrend(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 10,
        multiplier: float = 3.0,
    ) -> pd.Series:
        """Supertrend indicator — returns supertrend line values."""
        atr = IndicatorEngine._calc_atr(high, low, close, period)
        hl2 = (high + low) / 2
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        supertrend = pd.Series(np.nan, index=close.index)
        direction = pd.Series(1, index=close.index)  # 1=up, -1=down

        for i in range(1, len(close)):
            if close.iloc[i] > upper_band.iloc[i - 1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i - 1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]

        return supertrend

    @staticmethod
    def _calc_keltner(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20,
        multiplier: float = 1.5,
    ) -> tuple[pd.Series, pd.Series]:
        """Keltner Channels — upper, lower."""
        ema = close.ewm(span=period, adjust=False).mean()
        atr = IndicatorEngine._calc_atr(high, low, close, period)
        upper = ema + multiplier * atr
        lower = ema - multiplier * atr
        return upper, lower

    @staticmethod
    def _calc_williams_r(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Williams %R."""
        highest = high.rolling(period).max()
        lowest = low.rolling(period).min()
        wr = -100 * (highest - close) / (highest - lowest).replace(0, np.inf)
        return wr

    @staticmethod
    def _calc_cci(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20,
    ) -> pd.Series:
        """Commodity Channel Index."""
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        return (tp - sma_tp) / (0.015 * mad)

    @staticmethod
    def _calc_roc(close: pd.Series, period: int = 9) -> pd.Series:
        """Rate of Change."""
        return ((close - close.shift(period)) / close.shift(period)) * 100
