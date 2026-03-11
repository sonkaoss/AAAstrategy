"""MarketContextService — BTC state and overall market condition analysis.

Domain service (hexagonal architecture): no external library imports beyond
stdlib + numpy/pandas.  Only imports from domain ports.
"""
from __future__ import annotations

from nexus_strategy.domain.ports.config_port import IConfigProvider


class MarketContextService:
    """Analyzes BTC state and overall market conditions."""

    def __init__(self, config: IConfigProvider) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # analyze_btc
    # ------------------------------------------------------------------

    def analyze_btc(self, btc_indicators: dict[str, dict[str, float]]) -> dict:
        """Analyze BTC indicators across timeframes and return a structured summary.

        Parameters
        ----------
        btc_indicators:
            Dict with timeframe keys "1h", "4h", "1d", each mapping to a flat
            dict of indicator name -> float value.

        Returns
        -------
        dict with keys:
            price          – float: 1d close price
            change_1h      – float: pct change of 1h close vs 1h EMA_9 (0.0 if missing)
            change_24h     – float: pct change of 1d close vs 1d EMA_50 (0.0 if missing)
            above_ema200   – bool: 1d close > 1d EMA_200
            trend          – str: "bullish" | "bearish" | "neutral"
            golden_cross   – bool: 1d EMA_50 > 1d EMA_200
            death_cross    – bool: 1d EMA_50 < 1d EMA_200
        """
        ind_1h = btc_indicators.get("1h", {})
        ind_1d = btc_indicators.get("1d", {})

        # --- price ---
        price: float = ind_1d.get("close", 0.0)

        # --- change_1h ---
        close_1h = ind_1h.get("close", 0.0)
        ema9_1h = ind_1h.get("EMA_9", 0.0)
        if ema9_1h != 0.0:
            change_1h = (close_1h - ema9_1h) / ema9_1h * 100.0
        else:
            change_1h = 0.0

        # --- change_24h ---
        close_1d = ind_1d.get("close", 0.0)
        ema50_1d = ind_1d.get("EMA_50", 0.0)
        if ema50_1d != 0.0:
            change_24h = (close_1d - ema50_1d) / ema50_1d * 100.0
        else:
            change_24h = 0.0

        # --- above_ema200 ---
        ema200_1d = ind_1d.get("EMA_200", 0.0)
        above_ema200: bool = close_1d > ema200_1d

        # --- trend ---
        rsi_1d = ind_1d.get("RSI_14", 50.0)
        if above_ema200 and rsi_1d > 50:
            trend = "bullish"
        elif not above_ema200 and rsi_1d < 50:
            trend = "bearish"
        else:
            trend = "neutral"

        # --- golden_cross / death_cross ---
        golden_cross: bool = ema50_1d > ema200_1d
        death_cross: bool = ema50_1d < ema200_1d

        return {
            "price": price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "above_ema200": above_ema200,
            "trend": trend,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
        }

    # ------------------------------------------------------------------
    # analyze_market_phase
    # ------------------------------------------------------------------

    def analyze_market_phase(
        self,
        btc_analysis: dict,
        sentinel_data: dict,
    ) -> str:
        """Determine the current market phase from BTC analysis and sentiment data.

        Parameters
        ----------
        btc_analysis:
            Output of :meth:`analyze_btc`.
        sentinel_data:
            Dict with optional keys:
                risk_score      – float (0-100)
                fear_greed      – float (0-100)
                alt_performance – float (%, positive = alts outperforming)

        Returns
        -------
        One of: "BTC_RALLY", "ALT_RALLY", "FULL_BULL", "ROTATION",
                "RISK_OFF", "CAPITULATION", "RECOVERY", "MIXED"
        """
        trend: str = btc_analysis.get("trend", "neutral")
        risk_score: float = sentinel_data.get("risk_score", 0.0)
        fear_greed: float = sentinel_data.get("fear_greed", 50.0)
        alt_performance: float = sentinel_data.get("alt_performance", 0.0)

        # --- Capitulation ---
        if risk_score > 80 and trend == "bearish":
            return "CAPITULATION"

        # --- Risk-off ---
        if risk_score > 60 and trend == "bearish":
            return "RISK_OFF"

        # --- Full bull ---
        if trend == "bullish" and fear_greed > 60 and alt_performance > 0:
            return "FULL_BULL"

        # --- BTC Rally ---
        if trend == "bullish" and alt_performance <= 0:
            return "BTC_RALLY"

        # --- Alt Rally (alts significantly outperforming) ---
        if alt_performance > 5:
            return "ALT_RALLY"

        # --- Recovery ---
        if trend == "neutral" and 40 < fear_greed < 60:
            return "RECOVERY"

        # --- Rotation ---
        if trend == "neutral" and alt_performance != 0:
            return "ROTATION"

        # --- Fallback ---
        return "MIXED"

    # ------------------------------------------------------------------
    # calculate_altcoin_season_index
    # ------------------------------------------------------------------

    def calculate_altcoin_season_index(
        self,
        btc_change: float,
        alt_changes: dict[str, float],
    ) -> int:
        """Calculate an altcoin season index (0-100).

        Parameters
        ----------
        btc_change:
            BTC percentage change over the measurement period.
        alt_changes:
            Mapping of altcoin symbol -> percentage change over the same period.

        Returns
        -------
        Integer in [0, 100].  100 = all alts outperforming BTC.
        50 returned when *alt_changes* is empty.
        """
        if not alt_changes:
            return 50

        total_alts = len(alt_changes)
        outperformers = sum(1 for change in alt_changes.values() if change > btc_change)
        index = int(100 * outperformers / total_alts)

        # Clamp to [0, 100]
        return max(0, min(100, index))
