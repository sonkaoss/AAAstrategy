"""Tests for signal domain models."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.signal import (
    ExitLayer,
    Signal,
    ExitSignal,
    SignalBundle,
)


class TestExitLayer:
    def test_is_int_enum(self):
        from enum import IntEnum
        assert issubclass(ExitLayer, IntEnum)

    def test_values(self):
        assert ExitLayer.EMERGENCY == 1
        assert ExitLayer.TECHNICAL == 2
        assert ExitLayer.REGIME == 3
        assert ExitLayer.PORTFOLIO == 4
        assert ExitLayer.PROFIT_OPTIMIZER == 5

    def test_ordering(self):
        assert ExitLayer.EMERGENCY < ExitLayer.TECHNICAL
        assert ExitLayer.TECHNICAL < ExitLayer.REGIME
        assert ExitLayer.REGIME < ExitLayer.PORTFOLIO
        assert ExitLayer.PORTFOLIO < ExitLayer.PROFIT_OPTIMIZER


class TestSignal:
    def _make_signal(self, action="BUY", confidence=80, entry_price=100.0, stop_loss=95.0):
        return Signal(
            pair="BTC/USDT",
            strategy_name="momentum",
            action=action,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_levels=[{"price": 110.0, "pct": 0.5}],
            indicators_used=["rsi", "macd"],
            reasoning="Strong bullish signal",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def test_is_frozen(self):
        signal = self._make_signal()
        with pytest.raises((AttributeError, TypeError)):
            signal.confidence = 50  # type: ignore

    def test_is_buy_true(self):
        signal = self._make_signal(action="BUY", confidence=80)
        assert signal.is_buy is True

    def test_is_buy_false_no_signal(self):
        signal = self._make_signal(action="NO_SIGNAL", confidence=80)
        assert signal.is_buy is False

    def test_is_buy_false_zero_confidence(self):
        signal = self._make_signal(action="BUY", confidence=0)
        assert signal.is_buy is False

    def test_stop_loss_pct(self):
        # (stop_loss - entry_price) / entry_price = (95 - 100) / 100 = -0.05
        signal = self._make_signal(entry_price=100.0, stop_loss=95.0)
        assert abs(signal.stop_loss_pct - (-0.05)) < 1e-9

    def test_stop_loss_pct_zero_entry(self):
        signal = self._make_signal(entry_price=0.0, stop_loss=0.0)
        assert signal.stop_loss_pct == 0.0

    def test_stop_loss_pct_positive_entry(self):
        signal = self._make_signal(entry_price=200.0, stop_loss=190.0)
        assert abs(signal.stop_loss_pct - (-0.05)) < 1e-9


class TestExitSignal:
    def _make_exit_signal(self):
        return ExitSignal(
            should_exit=True,
            urgency=80,
            exit_layer=ExitLayer.EMERGENCY,
            partial_pct=1.0,
            reason="Stop loss hit",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def test_is_frozen(self):
        exit_signal = self._make_exit_signal()
        with pytest.raises((AttributeError, TypeError)):
            exit_signal.urgency = 50  # type: ignore

    def test_fields(self):
        es = self._make_exit_signal()
        assert es.should_exit is True
        assert es.urgency == 80
        assert es.exit_layer == ExitLayer.EMERGENCY
        assert es.partial_pct == 1.0
        assert es.reason == "Stop loss hit"

    def test_exit_layer_type(self):
        es = self._make_exit_signal()
        assert isinstance(es.exit_layer, ExitLayer)


class TestSignalBundle:
    def _make_bundle(self, action="BUY", composite_score=75, consensus_count=3, consensus_total=5):
        return SignalBundle(
            action=action,
            pair="ETH/USDT",
            composite_score=composite_score,
            consensus_count=consensus_count,
            consensus_total=consensus_total,
            source_signals=[],
            regime=None,
            suggested_stake_multiplier=1.0,
            weighted_stop_loss=0.95,
            merged_take_profits=[{"price": 110.0}],
            risk_rating="MEDIUM",
            reasoning="Consensus buy",
            sentinel_context={},
            expiry_candles=5,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def test_is_frozen(self):
        bundle = self._make_bundle()
        with pytest.raises((AttributeError, TypeError)):
            bundle.action = "REJECT"  # type: ignore

    def test_is_buy_true(self):
        bundle = self._make_bundle(action="BUY")
        assert bundle.is_buy is True

    def test_is_buy_false_reject(self):
        bundle = self._make_bundle(action="REJECT")
        assert bundle.is_buy is False

    def test_is_rejected(self):
        bundle = self._make_bundle(action="REJECT")
        assert bundle.is_rejected is True

    def test_is_rejected_false_for_buy(self):
        bundle = self._make_bundle(action="BUY")
        assert bundle.is_rejected is False

    def test_is_strong_buy_true(self):
        bundle = self._make_bundle(action="BUY", composite_score=70)
        assert bundle.is_strong_buy is True

    def test_is_strong_buy_false_below_70(self):
        bundle = self._make_bundle(action="BUY", composite_score=69)
        assert bundle.is_strong_buy is False

    def test_is_strong_buy_false_not_buy(self):
        bundle = self._make_bundle(action="REJECT", composite_score=90)
        assert bundle.is_strong_buy is False

    def test_consensus_ratio(self):
        bundle = self._make_bundle(consensus_count=3, consensus_total=5)
        assert abs(bundle.consensus_ratio - 0.6) < 1e-9

    def test_consensus_ratio_zero_total(self):
        bundle = self._make_bundle(consensus_count=0, consensus_total=0)
        assert bundle.consensus_ratio == 0.0

    def test_consensus_ratio_full(self):
        bundle = self._make_bundle(consensus_count=5, consensus_total=5)
        assert abs(bundle.consensus_ratio - 1.0) < 1e-9
