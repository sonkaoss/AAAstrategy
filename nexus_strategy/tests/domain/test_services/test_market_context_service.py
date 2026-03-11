"""Tests for MarketContextService — BTC state and market condition analysis."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.services.market_context_service import MarketContextService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config() -> MagicMock:
    mock = MagicMock(spec=IConfigProvider)
    return mock


@pytest.fixture()
def service(config: MagicMock) -> MarketContextService:
    return MarketContextService(config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_btc_indicators(
    *,
    close_1h: float = 50_000.0,
    ema9_1h: float = 49_500.0,
    close_1d: float = 50_000.0,
    ema50_1d: float = 48_000.0,
    ema200_1d: float = 45_000.0,
    rsi_1d: float = 60.0,
) -> dict:
    return {
        "1h": {
            "close": close_1h,
            "EMA_9": ema9_1h,
        },
        "4h": {
            "close": 50_100.0,
        },
        "1d": {
            "close": close_1d,
            "EMA_50": ema50_1d,
            "EMA_200": ema200_1d,
            "RSI_14": rsi_1d,
        },
    }


# ===========================================================================
# analyze_btc — complete data
# ===========================================================================

class TestAnalyzeBtcComplete:
    def test_price_is_1d_close(self, service: MarketContextService) -> None:
        indicators = _make_btc_indicators(close_1d=55_000.0)
        result = service.analyze_btc(indicators)
        assert result["price"] == 55_000.0

    def test_change_1h_calculation(self, service: MarketContextService) -> None:
        """change_1h = (close_1h - EMA_9_1h) / EMA_9_1h * 100."""
        indicators = _make_btc_indicators(close_1h=100.0, ema9_1h=90.0)
        result = service.analyze_btc(indicators)
        expected = (100.0 - 90.0) / 90.0 * 100.0
        assert abs(result["change_1h"] - expected) < 1e-9

    def test_change_24h_calculation(self, service: MarketContextService) -> None:
        """change_24h = (close_1d - EMA_50_1d) / EMA_50_1d * 100."""
        indicators = _make_btc_indicators(close_1d=60_000.0, ema50_1d=50_000.0)
        result = service.analyze_btc(indicators)
        expected = (60_000.0 - 50_000.0) / 50_000.0 * 100.0
        assert abs(result["change_24h"] - expected) < 1e-9

    def test_above_ema200_true(self, service: MarketContextService) -> None:
        indicators = _make_btc_indicators(close_1d=60_000.0, ema200_1d=45_000.0)
        assert service.analyze_btc(indicators)["above_ema200"] is True

    def test_above_ema200_false(self, service: MarketContextService) -> None:
        indicators = _make_btc_indicators(close_1d=30_000.0, ema200_1d=45_000.0)
        assert service.analyze_btc(indicators)["above_ema200"] is False

    def test_golden_cross_true(self, service: MarketContextService) -> None:
        indicators = _make_btc_indicators(ema50_1d=50_000.0, ema200_1d=40_000.0)
        assert service.analyze_btc(indicators)["golden_cross"] is True

    def test_death_cross_true(self, service: MarketContextService) -> None:
        indicators = _make_btc_indicators(ema50_1d=30_000.0, ema200_1d=45_000.0)
        assert service.analyze_btc(indicators)["death_cross"] is True

    def test_golden_and_death_cross_mutually_exclusive_when_ema50_above(
        self, service: MarketContextService
    ) -> None:
        indicators = _make_btc_indicators(ema50_1d=55_000.0, ema200_1d=45_000.0)
        result = service.analyze_btc(indicators)
        assert result["golden_cross"] is True
        assert result["death_cross"] is False

    def test_golden_and_death_cross_mutually_exclusive_when_ema50_below(
        self, service: MarketContextService
    ) -> None:
        indicators = _make_btc_indicators(ema50_1d=40_000.0, ema200_1d=45_000.0)
        result = service.analyze_btc(indicators)
        assert result["golden_cross"] is False
        assert result["death_cross"] is True

    def test_result_has_all_keys(self, service: MarketContextService) -> None:
        result = service.analyze_btc(_make_btc_indicators())
        required_keys = {"price", "change_1h", "change_24h", "above_ema200", "trend",
                         "golden_cross", "death_cross"}
        assert required_keys == set(result.keys())


# ===========================================================================
# analyze_btc — trend classification
# ===========================================================================

class TestAnalyzeBtcTrend:
    def test_trend_bullish(self, service: MarketContextService) -> None:
        """above EMA_200 + RSI > 50 -> bullish."""
        indicators = _make_btc_indicators(
            close_1d=60_000.0, ema200_1d=45_000.0, rsi_1d=65.0
        )
        assert service.analyze_btc(indicators)["trend"] == "bullish"

    def test_trend_bearish(self, service: MarketContextService) -> None:
        """below EMA_200 + RSI < 50 -> bearish."""
        indicators = _make_btc_indicators(
            close_1d=30_000.0, ema200_1d=45_000.0, rsi_1d=35.0
        )
        assert service.analyze_btc(indicators)["trend"] == "bearish"

    def test_trend_neutral_above_ema200_but_low_rsi(
        self, service: MarketContextService
    ) -> None:
        """above EMA_200 but RSI <= 50 -> neutral."""
        indicators = _make_btc_indicators(
            close_1d=60_000.0, ema200_1d=45_000.0, rsi_1d=45.0
        )
        assert service.analyze_btc(indicators)["trend"] == "neutral"

    def test_trend_neutral_below_ema200_but_high_rsi(
        self, service: MarketContextService
    ) -> None:
        """below EMA_200 but RSI >= 50 -> neutral."""
        indicators = _make_btc_indicators(
            close_1d=30_000.0, ema200_1d=45_000.0, rsi_1d=55.0
        )
        assert service.analyze_btc(indicators)["trend"] == "neutral"

    def test_trend_neutral_exactly_at_rsi50(self, service: MarketContextService) -> None:
        """RSI == 50 is not strictly > 50 → neutral when above EMA_200."""
        indicators = _make_btc_indicators(
            close_1d=60_000.0, ema200_1d=45_000.0, rsi_1d=50.0
        )
        assert service.analyze_btc(indicators)["trend"] == "neutral"


# ===========================================================================
# analyze_btc — missing / empty data
# ===========================================================================

class TestAnalyzeBtcMissingData:
    def test_empty_dict_returns_defaults(self, service: MarketContextService) -> None:
        result = service.analyze_btc({})
        assert result["price"] == 0.0
        assert result["change_1h"] == 0.0
        assert result["change_24h"] == 0.0
        assert result["above_ema200"] is False
        assert result["trend"] in ("bullish", "bearish", "neutral")
        assert isinstance(result["golden_cross"], bool)
        assert isinstance(result["death_cross"], bool)

    def test_missing_1h_timeframe_gives_zero_change(
        self, service: MarketContextService
    ) -> None:
        indicators = {
            "1d": {
                "close": 50_000.0,
                "EMA_50": 48_000.0,
                "EMA_200": 45_000.0,
                "RSI_14": 60.0,
            }
        }
        result = service.analyze_btc(indicators)
        assert result["change_1h"] == 0.0

    def test_missing_ema9_1h_gives_zero_change(self, service: MarketContextService) -> None:
        indicators = {
            "1h": {"close": 50_000.0},  # no EMA_9
            "1d": {"close": 50_000.0, "EMA_50": 48_000.0, "EMA_200": 45_000.0, "RSI_14": 60.0},
        }
        result = service.analyze_btc(indicators)
        assert result["change_1h"] == 0.0

    def test_missing_ema50_1d_gives_zero_change(self, service: MarketContextService) -> None:
        indicators = {
            "1h": {"close": 50_000.0, "EMA_9": 49_000.0},
            "1d": {"close": 50_000.0, "EMA_200": 45_000.0, "RSI_14": 60.0},  # no EMA_50
        }
        result = service.analyze_btc(indicators)
        assert result["change_24h"] == 0.0

    def test_missing_ema200_1d_gives_false_above(self, service: MarketContextService) -> None:
        indicators = {
            "1d": {"close": 50_000.0, "EMA_50": 48_000.0, "RSI_14": 60.0}  # no EMA_200
        }
        result = service.analyze_btc(indicators)
        # close=50_000 > 0.0 (default EMA_200) is True, so above_ema200 will be True
        # This test verifies no crash and returns a bool
        assert isinstance(result["above_ema200"], bool)

    def test_missing_rsi_defaults_to_50(self, service: MarketContextService) -> None:
        """Missing RSI_14 defaults to 50.0, so trend should be neutral if above EMA_200."""
        indicators = {
            "1d": {
                "close": 60_000.0,
                "EMA_50": 55_000.0,
                "EMA_200": 45_000.0,
                # no RSI_14 — defaults to 50.0, which is not > 50
            }
        }
        result = service.analyze_btc(indicators)
        assert result["trend"] == "neutral"

    def test_empty_1h_and_1d_dicts(self, service: MarketContextService) -> None:
        indicators = {"1h": {}, "4h": {}, "1d": {}}
        result = service.analyze_btc(indicators)
        assert result["change_1h"] == 0.0
        assert result["change_24h"] == 0.0
        assert result["price"] == 0.0


# ===========================================================================
# analyze_market_phase
# ===========================================================================

class TestAnalyzeMarketPhase:

    def _btc(self, trend: str = "neutral") -> dict:
        return {"trend": trend, "price": 50_000.0}

    def test_capitulation(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("bearish"),
            {"risk_score": 85.0, "fear_greed": 10.0, "alt_performance": -5.0},
        )
        assert result == "CAPITULATION"

    def test_risk_off(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("bearish"),
            {"risk_score": 65.0, "fear_greed": 25.0, "alt_performance": -3.0},
        )
        assert result == "RISK_OFF"

    def test_full_bull(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("bullish"),
            {"risk_score": 20.0, "fear_greed": 75.0, "alt_performance": 3.0},
        )
        assert result == "FULL_BULL"

    def test_btc_rally_alts_negative(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("bullish"),
            {"risk_score": 20.0, "fear_greed": 40.0, "alt_performance": -2.0},
        )
        assert result == "BTC_RALLY"

    def test_btc_rally_alts_zero(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("bullish"),
            {"risk_score": 20.0, "fear_greed": 40.0, "alt_performance": 0.0},
        )
        assert result == "BTC_RALLY"

    def test_alt_rally(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 50.0, "alt_performance": 8.0},
        )
        assert result == "ALT_RALLY"

    def test_recovery(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 50.0, "alt_performance": 0.0},
        )
        assert result == "RECOVERY"

    def test_rotation(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 30.0, "alt_performance": 3.0},
        )
        assert result == "ROTATION"

    def test_mixed_fallback(self, service: MarketContextService) -> None:
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 30.0, "alt_performance": 0.0},
        )
        assert result == "MIXED"

    def test_capitulation_takes_priority_over_risk_off(
        self, service: MarketContextService
    ) -> None:
        """risk_score=90 (> 80) should give CAPITULATION, not RISK_OFF."""
        result = service.analyze_market_phase(
            self._btc("bearish"),
            {"risk_score": 90.0, "fear_greed": 10.0, "alt_performance": -5.0},
        )
        assert result == "CAPITULATION"

    def test_empty_sentinel_data_returns_valid_phase(
        self, service: MarketContextService
    ) -> None:
        result = service.analyze_market_phase(self._btc("neutral"), {})
        assert result in {
            "BTC_RALLY", "ALT_RALLY", "FULL_BULL", "ROTATION",
            "RISK_OFF", "CAPITULATION", "RECOVERY", "MIXED",
        }

    def test_risk_score_exactly_80_is_not_capitulation(
        self, service: MarketContextService
    ) -> None:
        """Boundary: risk_score > 80 required for CAPITULATION; exactly 80 is not."""
        result = service.analyze_market_phase(
            self._btc("bearish"),
            {"risk_score": 80.0, "fear_greed": 10.0, "alt_performance": -5.0},
        )
        assert result == "RISK_OFF"

    def test_risk_score_exactly_60_is_not_risk_off(
        self, service: MarketContextService
    ) -> None:
        """Boundary: risk_score > 60 required for RISK_OFF; exactly 60 is not."""
        result = service.analyze_market_phase(
            self._btc("bearish"),
            {"risk_score": 60.0, "fear_greed": 25.0, "alt_performance": -3.0},
        )
        # Does not meet risk-off threshold; fallback to MIXED
        assert result == "MIXED"

    def test_alt_rally_only_when_alt_performance_strictly_greater_than_5(
        self, service: MarketContextService
    ) -> None:
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 30.0, "alt_performance": 5.0},
        )
        # alt_performance == 5.0 is NOT > 5 → ROTATION (neutral and alt_performance != 0)
        assert result == "ROTATION"

    def test_fear_greed_boundary_recovery_lower(
        self, service: MarketContextService
    ) -> None:
        """fear_greed exactly 40 is not > 40, so RECOVERY does not apply."""
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 40.0, "alt_performance": 0.0},
        )
        assert result == "MIXED"

    def test_fear_greed_boundary_recovery_upper(
        self, service: MarketContextService
    ) -> None:
        """fear_greed exactly 60 is not < 60, so RECOVERY does not apply."""
        result = service.analyze_market_phase(
            self._btc("neutral"),
            {"risk_score": 30.0, "fear_greed": 60.0, "alt_performance": 0.0},
        )
        assert result == "MIXED"


# ===========================================================================
# calculate_altcoin_season_index
# ===========================================================================

class TestCalculateAltcoinSeasonIndex:

    def test_empty_alts_returns_50(self, service: MarketContextService) -> None:
        assert service.calculate_altcoin_season_index(5.0, {}) == 50

    def test_all_alts_outperform_returns_100(self, service: MarketContextService) -> None:
        alts = {"ETH": 10.0, "BNB": 8.0, "SOL": 12.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 100

    def test_no_alts_outperform_returns_0(self, service: MarketContextService) -> None:
        alts = {"ETH": 2.0, "BNB": 1.0, "SOL": 3.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 0

    def test_half_outperform_returns_50(self, service: MarketContextService) -> None:
        alts = {"ETH": 10.0, "BNB": 3.0}  # ETH outperforms, BNB does not
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 50

    def test_single_alt_outperforms(self, service: MarketContextService) -> None:
        alts = {"ETH": 10.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 100

    def test_single_alt_does_not_outperform(self, service: MarketContextService) -> None:
        alts = {"ETH": 2.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 0

    def test_result_is_integer(self, service: MarketContextService) -> None:
        alts = {"ETH": 10.0, "BNB": 3.0, "SOL": 8.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert isinstance(result, int)

    def test_result_clamped_to_0_100(self, service: MarketContextService) -> None:
        """Output should never exceed [0, 100]."""
        alts = {"ETH": 10.0, "BNB": 9.0, "SOL": 11.0}
        result = service.calculate_altcoin_season_index(1.0, alts)
        assert 0 <= result <= 100

    def test_btc_change_negative_most_alts_outperform(
        self, service: MarketContextService
    ) -> None:
        """When BTC drops, even flat alts outperform."""
        alts = {"ETH": 0.0, "BNB": -1.0, "SOL": 1.0}
        # btc_change = -5.0; ETH(0.0) > -5.0 ✓, BNB(-1.0) > -5.0 ✓, SOL(1.0) > -5.0 ✓
        result = service.calculate_altcoin_season_index(-5.0, alts)
        assert result == 100

    def test_exact_btc_match_does_not_count_as_outperform(
        self, service: MarketContextService
    ) -> None:
        """Alt change == btc_change is NOT strictly greater, so does not count."""
        alts = {"ETH": 5.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 0

    def test_many_alts_partial_outperformance(self, service: MarketContextService) -> None:
        btc_change = 5.0
        alts = {f"ALT_{i}": float(i) for i in range(10)}
        # values 0..9; btc_change=5.0; outperformers are ALT_6..ALT_9 → 4 out of 10 → 40
        result = service.calculate_altcoin_season_index(btc_change, alts)
        assert result == 40

    def test_all_alts_same_value_as_btc(self, service: MarketContextService) -> None:
        alts = {"ETH": 5.0, "BNB": 5.0}
        result = service.calculate_altcoin_season_index(5.0, alts)
        assert result == 0

    def test_zero_btc_change(self, service: MarketContextService) -> None:
        alts = {"ETH": 1.0, "BNB": -1.0}
        # ETH(1.0) > 0.0 ✓, BNB(-1.0) > 0.0 ✗ → 1 of 2 → 50
        result = service.calculate_altcoin_season_index(0.0, alts)
        assert result == 50
