"""Tests for risk domain models."""
from __future__ import annotations

import pytest

from nexus_strategy.domain.models.risk import (
    DrawdownLevel,
    PositionAction,
    PortfolioState,
)


class TestDrawdownLevel:
    def test_is_int_enum(self):
        from enum import IntEnum
        assert issubclass(DrawdownLevel, IntEnum)

    def test_values(self):
        assert DrawdownLevel.NORMAL == 1
        assert DrawdownLevel.CAUTION == 2
        assert DrawdownLevel.WARNING == 3
        assert DrawdownLevel.CRITICAL == 4
        assert DrawdownLevel.CATASTROPHIC == 5

    def test_ordering(self):
        assert DrawdownLevel.NORMAL < DrawdownLevel.CAUTION
        assert DrawdownLevel.CAUTION < DrawdownLevel.WARNING
        assert DrawdownLevel.WARNING < DrawdownLevel.CRITICAL
        assert DrawdownLevel.CRITICAL < DrawdownLevel.CATASTROPHIC

    def test_from_drawdown_normal(self):
        assert DrawdownLevel.from_drawdown(0.0) == DrawdownLevel.NORMAL
        assert DrawdownLevel.from_drawdown(0.04) == DrawdownLevel.NORMAL
        assert DrawdownLevel.from_drawdown(0.049) == DrawdownLevel.NORMAL

    def test_from_drawdown_caution(self):
        assert DrawdownLevel.from_drawdown(0.05) == DrawdownLevel.CAUTION
        assert DrawdownLevel.from_drawdown(0.07) == DrawdownLevel.CAUTION
        assert DrawdownLevel.from_drawdown(0.099) == DrawdownLevel.CAUTION

    def test_from_drawdown_warning(self):
        assert DrawdownLevel.from_drawdown(0.10) == DrawdownLevel.WARNING
        assert DrawdownLevel.from_drawdown(0.12) == DrawdownLevel.WARNING
        assert DrawdownLevel.from_drawdown(0.149) == DrawdownLevel.WARNING

    def test_from_drawdown_critical(self):
        assert DrawdownLevel.from_drawdown(0.15) == DrawdownLevel.CRITICAL
        assert DrawdownLevel.from_drawdown(0.17) == DrawdownLevel.CRITICAL
        assert DrawdownLevel.from_drawdown(0.199) == DrawdownLevel.CRITICAL

    def test_from_drawdown_catastrophic(self):
        assert DrawdownLevel.from_drawdown(0.20) == DrawdownLevel.CATASTROPHIC
        assert DrawdownLevel.from_drawdown(0.50) == DrawdownLevel.CATASTROPHIC
        assert DrawdownLevel.from_drawdown(1.0) == DrawdownLevel.CATASTROPHIC


class TestPositionAction:
    def test_not_frozen(self):
        pa = PositionAction(action="HOLD", amount=100.0, reason="No change", urgency=0)
        pa.action = "SELL"
        assert pa.action == "SELL"

    def test_fields(self):
        pa = PositionAction(action="BUY", amount=500.0, reason="Strong signal", urgency=80)
        assert pa.action == "BUY"
        assert pa.amount == 500.0
        assert pa.reason == "Strong signal"
        assert pa.urgency == 80


class TestPortfolioState:
    def _make_portfolio(self, total_equity=10000.0, total_exposure=3000.0):
        return PortfolioState(
            total_equity=total_equity,
            peak_equity=11000.0,
            current_drawdown=0.09,
            drawdown_level=DrawdownLevel.CAUTION,
            open_positions=[{"pair": "BTC/USDT"}],
            total_exposure=total_exposure,
            cash_available=7000.0,
            var_95=500.0,
            cvar_95=700.0,
            correlation_matrix={},
            sector_distribution={},
            recovery_mode=False,
            recovery_progress=0.0,
        )

    def test_not_frozen(self):
        portfolio = self._make_portfolio()
        portfolio.recovery_mode = True
        assert portfolio.recovery_mode is True

    def test_exposure_ratio(self):
        portfolio = self._make_portfolio(total_equity=10000.0, total_exposure=3000.0)
        assert abs(portfolio.exposure_ratio - 0.3) < 1e-9

    def test_exposure_ratio_zero_equity(self):
        portfolio = self._make_portfolio(total_equity=0.0, total_exposure=0.0)
        assert portfolio.exposure_ratio == 0.0

    def test_exposure_ratio_full(self):
        portfolio = self._make_portfolio(total_equity=10000.0, total_exposure=10000.0)
        assert abs(portfolio.exposure_ratio - 1.0) < 1e-9

    def test_fields(self):
        portfolio = self._make_portfolio()
        assert portfolio.total_equity == 10000.0
        assert portfolio.drawdown_level == DrawdownLevel.CAUTION
        assert portfolio.recovery_mode is False
