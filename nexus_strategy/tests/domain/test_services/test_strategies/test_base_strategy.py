"""Tests for BaseStrategy ABC."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    CompositeRegime,
    MacroRegime,
    MicroRegime,
    MidRegime,
    SynthesizedRegime,
)
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy


# ---------------------------------------------------------------------------
# Concrete subclass for testing
# ---------------------------------------------------------------------------

class _DummyStrategy(BaseStrategy):
    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        return self._no_signal(pair)

    def generate_exit_signal(
        self, pair: str, market_state: MarketState, entry_price: float, current_pnl_pct: float
    ) -> ExitSignal:
        return self._no_exit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_market_state(pair: str = "BTC/USDT", indicators_5m: dict | None = None) -> MarketState:
    ind_5m = indicators_5m or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=SynthesizedRegime.REGIME_MODERATE_BULL,
        confidence=70,
        duration_candles=5,
        transition_probability=0.0,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={pair: {"5m": ind_5m, "15m": {}, "1h": {}}},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=False,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=1.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=60,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBaseStrategyABC:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseStrategy("test", [])  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        strat = _DummyStrategy("Dummy", [SynthesizedRegime.REGIME_STRONG_BULL])
        assert strat.name == "Dummy"

    def test_name_property(self) -> None:
        strat = _DummyStrategy("Test", [])
        assert strat.name == "Test"

    def test_optimal_regimes_property(self) -> None:
        regimes = [SynthesizedRegime.REGIME_STRONG_BULL, SynthesizedRegime.REGIME_SQUEEZE]
        strat = _DummyStrategy("Test", regimes)
        assert strat.optimal_regimes == regimes

    def test_optimal_regimes_returns_copy(self) -> None:
        regimes = [SynthesizedRegime.REGIME_STRONG_BULL]
        strat = _DummyStrategy("Test", regimes)
        result = strat.optimal_regimes
        result.append(SynthesizedRegime.REGIME_PANIC)
        assert len(strat.optimal_regimes) == 1


class TestIsActiveForRegime:
    def test_active_when_regime_in_optimal(self) -> None:
        strat = _DummyStrategy("Test", [SynthesizedRegime.REGIME_STRONG_BULL])
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is True

    def test_inactive_when_regime_not_in_optimal(self) -> None:
        strat = _DummyStrategy("Test", [SynthesizedRegime.REGIME_STRONG_BULL])
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_PANIC) is False

    def test_inactive_when_no_optimal_regimes(self) -> None:
        strat = _DummyStrategy("Test", [])
        assert strat.is_active_for_regime(SynthesizedRegime.REGIME_STRONG_BULL) is False


class TestNoSignalHelper:
    def test_no_signal_returns_signal(self) -> None:
        strat = _DummyStrategy("Dummy", [])
        ms = _make_market_state()
        sig = strat.generate_signal("ETH/USDT", ms)
        assert isinstance(sig, Signal)
        assert sig.action == "NO_SIGNAL"
        assert sig.confidence == 0
        assert sig.pair == "ETH/USDT"
        assert sig.strategy_name == "Dummy"
        assert sig.is_buy is False


class TestNoExitHelper:
    def test_no_exit_returns_exit_signal(self) -> None:
        strat = _DummyStrategy("Dummy", [])
        ms = _make_market_state()
        ex = strat.generate_exit_signal("ETH/USDT", ms, 100.0, 0.0)
        assert isinstance(ex, ExitSignal)
        assert ex.should_exit is False
        assert ex.urgency == 0


class TestGetHelper:
    def test_get_existing_indicator(self) -> None:
        ms = _make_market_state(indicators_5m={"RSI_14": 55.0})
        val = BaseStrategy._get(ms, "BTC/USDT", "5m", "RSI_14")
        assert val == 55.0

    def test_get_missing_indicator_returns_default(self) -> None:
        ms = _make_market_state()
        val = BaseStrategy._get(ms, "BTC/USDT", "5m", "RSI_14", 42.0)
        assert val == 42.0

    def test_get_missing_pair_returns_default(self) -> None:
        ms = _make_market_state()
        val = BaseStrategy._get(ms, "UNKNOWN/PAIR", "5m", "RSI_14")
        assert val == 0.0
