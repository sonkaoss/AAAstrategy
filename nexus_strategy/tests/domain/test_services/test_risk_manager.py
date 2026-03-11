"""Tests for RiskManager — portfolio-level risk management service."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.models.signal import SignalBundle
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    SynthesizedRegime,
    CompositeRegime,
    MicroRegime,
    MidRegime,
    MacroRegime,
)
from nexus_strategy.domain.services.risk_manager import RiskManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> MagicMock:
    """Return a mock IConfigProvider."""
    return MagicMock(spec=IConfigProvider)


def _make_composite_regime(synthesized: SynthesizedRegime) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=80,
        duration_candles=5,
        transition_probability=0.1,
        recommended_strategies=["momentum"],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )


def _make_market_state(
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_MODERATE_BULL,
    sentinel_risk: int = 30,
) -> MarketState:
    """Return a minimal MarketState mock."""
    regime = _make_composite_regime(synthesized)
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={"risk_score": sentinel_risk},
        sentinel_connected=True,
        sentinel_data_age_seconds=10,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=2.0,
        btc_above_ema200=True,
        btc_trend="up",
        market_phase="markup",
        altcoin_season_index=60,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _make_signal_bundle(
    pair: str = "BTC/USDT",
    composite_score: int = 75,
) -> SignalBundle:
    """Return a minimal SignalBundle mock."""
    return SignalBundle(
        action="BUY",
        pair=pair,
        composite_score=composite_score,
        consensus_count=3,
        consensus_total=4,
        source_signals=[],
        regime=None,
        suggested_stake_multiplier=1.0,
        weighted_stop_loss=48000.0,
        merged_take_profits=[],
        risk_rating="MEDIUM",
        reasoning="Test signal",
        sentinel_context={},
        expiry_candles=12,
        created_at=datetime.now(timezone.utc),
    )


def _base_portfolio_state(
    drawdown_pct: float = 0.0,
    open_positions: int = 0,
    open_pairs: list[str] | None = None,
    total_exposure: float = 0.30,
    sector_exposure: dict | None = None,
) -> dict:
    return {
        "current_drawdown_pct": drawdown_pct,
        "open_positions": open_positions,
        "open_pairs": open_pairs or [],
        "total_exposure": total_exposure,
        "sector_exposure": sector_exposure or {},
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config() -> MagicMock:
    return _make_config()


@pytest.fixture()
def manager(config: MagicMock) -> RiskManager:
    return RiskManager(config)


# ---------------------------------------------------------------------------
# validate_entry tests
# ---------------------------------------------------------------------------

class TestValidateEntry:

    def test_validate_entry_allowed(self, manager: RiskManager) -> None:
        """All checks pass — entry should be allowed."""
        bundle = _make_signal_bundle("ETH/USDT", composite_score=75)
        market = _make_market_state(
            synthesized=SynthesizedRegime.REGIME_MODERATE_BULL,
            sentinel_risk=30,
        )
        portfolio = _base_portfolio_state(
            drawdown_pct=2.0,
            open_positions=3,
            open_pairs=["BTC/USDT"],
            total_exposure=0.30,
            sector_exposure={"L1": 0.20},
        )
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is True
        assert reason == "Entry allowed"

    def test_reject_catastrophic_drawdown(self, manager: RiskManager) -> None:
        """Drawdown >= 20% (level 4) must be rejected regardless of score."""
        bundle = _make_signal_bundle("BTC/USDT", composite_score=95)
        market = _make_market_state()
        portfolio = _base_portfolio_state(drawdown_pct=22.0)
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Catastrophic drawdown - no entries"

    def test_reject_critical_drawdown_low_confidence(self, manager: RiskManager) -> None:
        """Drawdown level 3 + composite_score <= 80 must be rejected."""
        bundle = _make_signal_bundle("BTC/USDT", composite_score=70)
        market = _make_market_state()
        portfolio = _base_portfolio_state(drawdown_pct=16.0)
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Critical drawdown - only high confidence entries"

    def test_allow_critical_drawdown_high_confidence(self, manager: RiskManager) -> None:
        """Drawdown level 3 but composite_score > 80 should pass this check."""
        bundle = _make_signal_bundle("BTC/USDT", composite_score=85)
        market = _make_market_state(
            synthesized=SynthesizedRegime.REGIME_MODERATE_BULL,
            sentinel_risk=30,
        )
        portfolio = _base_portfolio_state(
            drawdown_pct=16.0,
            open_positions=0,
            total_exposure=0.20,
        )
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is True
        assert reason == "Entry allowed"

    def test_reject_max_slots(self, manager: RiskManager) -> None:
        """Open positions at max slots must be rejected."""
        bundle = _make_signal_bundle("ETH/USDT", composite_score=75)
        # MODERATE_BULL allows 10 slots
        market = _make_market_state(synthesized=SynthesizedRegime.REGIME_MODERATE_BULL)
        portfolio = _base_portfolio_state(open_positions=10)
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Maximum position slots reached"

    def test_reject_pair_already_open(self, manager: RiskManager) -> None:
        """If the pair already has an open position, reject."""
        bundle = _make_signal_bundle("SOL/USDT", composite_score=75)
        market = _make_market_state()
        portfolio = _base_portfolio_state(
            open_positions=2,
            open_pairs=["BTC/USDT", "SOL/USDT"],
        )
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Pair already has open position"

    def test_reject_max_exposure(self, manager: RiskManager) -> None:
        """total_exposure >= 0.85 must be rejected."""
        bundle = _make_signal_bundle("BTC/USDT", composite_score=75)
        market = _make_market_state()
        portfolio = _base_portfolio_state(total_exposure=0.90)
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Maximum portfolio exposure reached"

    def test_reject_sentinel_risk(self, manager: RiskManager) -> None:
        """Sentinel risk_score >= 80 must be rejected."""
        bundle = _make_signal_bundle("BTC/USDT", composite_score=75)
        market = _make_market_state(sentinel_risk=85)
        portfolio = _base_portfolio_state()
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Sentinel risk too high"

    def test_reject_sector_concentration(self, manager: RiskManager) -> None:
        """Sector exposure >= 0.35 for the signal's sector must be rejected."""
        # BTC/USDT is in L1 sector
        bundle = _make_signal_bundle("BTC/USDT", composite_score=75)
        market = _make_market_state()
        portfolio = _base_portfolio_state(
            sector_exposure={"L1": 0.40},
        )
        allowed, reason = manager.validate_entry(bundle, market, portfolio)
        assert allowed is False
        assert reason == "Sector concentration limit reached"


# ---------------------------------------------------------------------------
# get_drawdown_level tests
# ---------------------------------------------------------------------------

class TestGetDrawdownLevel:

    def test_drawdown_level_normal(self, manager: RiskManager) -> None:
        """0% drawdown -> level 0 (NORMAL)."""
        assert manager.get_drawdown_level(0.0) == 0

    def test_drawdown_level_caution(self, manager: RiskManager) -> None:
        """7% drawdown -> level 1 (CAUTION)."""
        assert manager.get_drawdown_level(7.0) == 1

    def test_drawdown_level_warning(self, manager: RiskManager) -> None:
        """12% drawdown -> level 2 (WARNING)."""
        assert manager.get_drawdown_level(12.0) == 2

    def test_drawdown_level_critical(self, manager: RiskManager) -> None:
        """17% drawdown -> level 3 (CRITICAL)."""
        assert manager.get_drawdown_level(17.0) == 3

    def test_drawdown_level_catastrophic(self, manager: RiskManager) -> None:
        """25% drawdown -> level 4 (CATASTROPHIC)."""
        assert manager.get_drawdown_level(25.0) == 4

    def test_drawdown_boundary_exactly_5(self, manager: RiskManager) -> None:
        """Exactly 5% -> level 1 (CAUTION, not NORMAL)."""
        assert manager.get_drawdown_level(5.0) == 1

    def test_drawdown_boundary_exactly_20(self, manager: RiskManager) -> None:
        """Exactly 20% -> level 4 (CATASTROPHIC)."""
        assert manager.get_drawdown_level(20.0) == 4


# ---------------------------------------------------------------------------
# get_max_slots tests
# ---------------------------------------------------------------------------

class TestGetMaxSlots:

    def test_max_slots_strong_bull(self, manager: RiskManager) -> None:
        """STRONG_BULL -> 12 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_STRONG_BULL) == 12

    def test_max_slots_breakout_bull(self, manager: RiskManager) -> None:
        """BREAKOUT_BULL -> 12 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_BREAKOUT_BULL) == 12

    def test_max_slots_euphoria(self, manager: RiskManager) -> None:
        """EUPHORIA -> 12 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_EUPHORIA) == 12

    def test_max_slots_moderate_bull(self, manager: RiskManager) -> None:
        """MODERATE_BULL -> 10 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_MODERATE_BULL) == 10

    def test_max_slots_weak_bull(self, manager: RiskManager) -> None:
        """WEAK_BULL -> 8 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_WEAK_BULL) == 8

    def test_max_slots_ranging_tight(self, manager: RiskManager) -> None:
        """RANGING_TIGHT -> 8 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_RANGING_TIGHT) == 8

    def test_max_slots_weak_bear(self, manager: RiskManager) -> None:
        """WEAK_BEAR -> 5 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_WEAK_BEAR) == 5

    def test_max_slots_moderate_bear(self, manager: RiskManager) -> None:
        """MODERATE_BEAR -> 5 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_MODERATE_BEAR) == 5

    def test_max_slots_panic(self, manager: RiskManager) -> None:
        """PANIC -> 2 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_PANIC) == 2

    def test_max_slots_default(self, manager: RiskManager) -> None:
        """Unknown regime falls back to 8 slots."""
        assert manager.get_max_slots(SynthesizedRegime.REGIME_UNCERTAIN) == 8


# ---------------------------------------------------------------------------
# calculate_portfolio_risk tests
# ---------------------------------------------------------------------------

class TestCalculatePortfolioRisk:

    def test_portfolio_risk_empty(self, manager: RiskManager) -> None:
        """Empty positions list -> all zeros."""
        result = manager.calculate_portfolio_risk([])
        assert result["total_exposure"] == 0
        assert result["var_95"] == 0
        assert result["sector_distribution"] == {}
        assert result["position_count"] == 0

    def test_portfolio_risk_calculation(self, manager: RiskManager) -> None:
        """Standard positions -> correct totals and sector distribution."""
        positions = [
            {"pair": "BTC/USDT", "size": 0.10, "pnl_pct": 5.0},
            {"pair": "ETH/USDT", "size": 0.08, "pnl_pct": -2.0},
            {"pair": "UNI/USDT", "size": 0.05, "pnl_pct": 1.0},
        ]
        result = manager.calculate_portfolio_risk(positions)

        assert result["position_count"] == 3
        assert abs(result["total_exposure"] - 0.23) < 1e-9
        assert abs(result["var_95"] - (-2.0 * 0.23)) < 1e-9
        # BTC and ETH are L1, UNI is DEFI
        assert result["sector_distribution"]["L1"] == 2
        assert result["sector_distribution"]["DEFI"] == 1

    def test_portfolio_risk_single_position(self, manager: RiskManager) -> None:
        """Single position returns correct metrics."""
        positions = [{"pair": "SOL/USDT", "size": 0.15, "pnl_pct": 10.0}]
        result = manager.calculate_portfolio_risk(positions)
        assert result["position_count"] == 1
        assert result["total_exposure"] == 0.15
        assert result["var_95"] == pytest.approx(-0.30)
        assert result["sector_distribution"] == {"L1": 1}

    def test_portfolio_risk_unknown_pair_sector(self, manager: RiskManager) -> None:
        """Pairs not in SECTOR_MAP are excluded from sector_distribution."""
        positions = [
            {"pair": "UNKNOWN/USDT", "size": 0.10, "pnl_pct": 0.0},
        ]
        result = manager.calculate_portfolio_risk(positions)
        assert result["total_exposure"] == 0.10
        assert result["sector_distribution"] == {}
