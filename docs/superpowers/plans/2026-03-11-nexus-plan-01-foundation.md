# Nexus Strategy - Plan 1: Foundation (Hexagonal Architecture)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational layer with Hexagonal Architecture — domain models, port interfaces, utility functions, configuration adapter, and dependency injection container.

**Architecture:** Hexagonal (Ports & Adapters). Domain core has ZERO external dependencies. All external interactions through abstract port interfaces. Bottom-up: models → ports → utils → config adapter → DI container.

**Tech Stack:** Python 3.11+, pydantic for validation, tomllib for TOML parsing, watchdog for hot-reload, structlog for logging, pytest for testing.

**Spec Reference:** `docs/superpowers/specs/2026-03-11-nexus-strategy-design.md`

---

## File Structure

```
nexus_strategy/
├── __init__.py                              # Package init, version
├── domain/                                  # ══ INNER CORE ══ (ZERO external deps)
│   ├── __init__.py
│   ├── models/                              # Immutable data models
│   │   ├── __init__.py
│   │   ├── regime.py                        # Regime enums + CompositeRegime
│   │   ├── signal.py                        # Signal, ExitSignal, SignalBundle
│   │   ├── risk.py                          # PortfolioState, PositionAction, DrawdownLevel
│   │   ├── trade_context.py                 # TradeContext dataclass
│   │   └── market_state.py                  # MarketState frozen snapshot
│   └── ports/                               # Abstract interfaces (ABCs)
│       ├── __init__.py
│       ├── data_port.py                     # IDataProvider, IIndicatorEngine
│       ├── sentinel_port.py                 # ISentinelProvider
│       ├── config_port.py                   # IConfigProvider
│       ├── storage_port.py                  # IStorageProvider
│       ├── analytics_port.py                # IAnalyticsEmitter
│       └── trade_repo_port.py               # ITradeRepository
├── application/                             # ══ MIDDLE RING ══ (orchestration)
│   ├── __init__.py
│   └── dependency_container.py              # DI container (wires ports→adapters)
├── adapters/                                # ══ OUTER RING ══ (external connections)
│   ├── __init__.py
│   └── config/                              # Configuration adapter
│       ├── __init__.py
│       ├── toml_adapter.py                  # TOML loading + hot-reload + profiles
│       └── config_schema.py                 # Pydantic validation schemas
├── config/                                  # Configuration files (not code)
│   ├── base.toml
│   └── profiles/
│       ├── conservative.toml
│       ├── balanced.toml
│       ├── aggressive.toml
│       └── bear_market.toml
├── utils/                                   # Pure utility functions
│   ├── __init__.py
│   ├── math_utils.py
│   ├── cache.py
│   ├── decorators.py
│   └── constants.py
└── tests/
    ├── __init__.py
    ├── domain/
    │   ├── __init__.py
    │   ├── test_models/
    │   │   ├── __init__.py
    │   │   ├── test_regime.py
    │   │   ├── test_signal.py
    │   │   ├── test_risk.py
    │   │   ├── test_trade_context.py
    │   │   └── test_market_state.py
    │   └── test_ports/
    │       ├── __init__.py
    │       └── test_port_contracts.py
    ├── adapters/
    │   ├── __init__.py
    │   └── test_config/
    │       ├── __init__.py
    │       ├── test_config_schema.py
    │       └── test_toml_adapter.py
    ├── application/
    │   ├── __init__.py
    │   └── test_dependency_container.py
    └── utils/
        ├── __init__.py
        ├── test_math_utils.py
        ├── test_cache.py
        └── test_decorators.py
```

---

## Chunk 1: Scaffolding, Regime Models, Signal Models

### Task 1: Project Scaffolding

**Files:**
- Create: All `__init__.py` files and directory structure
- Create: `requirements.txt`

- [ ] **Step 1: Create hexagonal directory structure**

```bash
cd "/home/atabey/Belgeler/Snake oyunu/claude"
mkdir -p nexus_strategy/{domain/{models,ports,services,strategies},application,adapters/{freqtrade,sentinel,config,storage,analytics},config/profiles,sentinel_engine/{data_collectors,analyzers},utils,tests/{domain/{test_models,test_ports},adapters/test_config,application,utils}}
```

- [ ] **Step 2: Create package init files**

`nexus_strategy/__init__.py`:
```python
"""Nexus Trading Strategy - Multi-Strategy Ensemble with Self-Learning.

Hexagonal Architecture: Domain (inner) → Application (middle) → Adapters (outer)
"""

__version__ = "1.0.0"
__author__ = "Nexus Team"
```

All other `__init__.py` files: empty.

- [ ] **Step 3: Create requirements.txt**

```
# Core
pandas>=2.0.0
numpy>=1.24.0
ta-lib>=0.4.28
pandas-ta>=0.3.14b
scipy>=1.10.0

# Configuration
pydantic>=2.0.0
watchdog>=3.0.0

# Logging
structlog>=23.0.0

# Sentinel Engine
aiohttp>=3.9.0
websockets>=12.0
ccxt>=4.0.0
redis>=5.0.0
orjson>=3.9.0
aiosqlite>=0.19.0

# Analytics
prometheus-client>=0.19.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
hypothesis>=6.90.0
```

- [ ] **Step 4: Verify structure**

```bash
find nexus_strategy -type d | sort
```

- [ ] **Step 5: Commit**

```bash
git init
git add nexus_strategy/ requirements.txt
git commit -m "feat: scaffold Nexus strategy with hexagonal architecture"
```

---

### Task 2: Regime Models

**Files:**
- Create: `nexus_strategy/domain/models/regime.py`
- Test: `nexus_strategy/tests/domain/test_models/test_regime.py`

- [ ] **Step 1: Write failing tests for regime enums**

`nexus_strategy/tests/domain/test_models/test_regime.py`:
```python
"""Tests for regime model definitions."""
import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from nexus_strategy.domain.models.regime import (
    MicroRegime,
    MidRegime,
    MacroRegime,
    SynthesizedRegime,
    CompositeRegime,
)


class TestMicroRegime:
    def test_has_all_8_micro_regimes(self):
        assert len(MicroRegime) == 8

    def test_trending_up_exists(self):
        assert MicroRegime.MICRO_TRENDING_UP.value == "micro_trending_up"

    def test_trending_down_exists(self):
        assert MicroRegime.MICRO_TRENDING_DOWN.value == "micro_trending_down"

    def test_ranging_exists(self):
        assert MicroRegime.MICRO_RANGING.value == "micro_ranging"

    def test_volatile_exists(self):
        assert MicroRegime.MICRO_VOLATILE.value == "micro_volatile"

    def test_squeeze_exists(self):
        assert MicroRegime.MICRO_SQUEEZE.value == "micro_squeeze"

    def test_breakout_up_exists(self):
        assert MicroRegime.MICRO_BREAKOUT_UP.value == "micro_breakout_up"

    def test_breakout_down_exists(self):
        assert MicroRegime.MICRO_BREAKOUT_DOWN.value == "micro_breakout_down"

    def test_choppy_exists(self):
        assert MicroRegime.MICRO_CHOPPY.value == "micro_choppy"


class TestMidRegime:
    def test_has_all_10_mid_regimes(self):
        assert len(MidRegime) == 10

    def test_trend_bull_strong_exists(self):
        assert MidRegime.TREND_BULL_STRONG.value == "trend_bull_strong"

    def test_accumulation_exists(self):
        assert MidRegime.ACCUMULATION.value == "accumulation"

    def test_distribution_exists(self):
        assert MidRegime.DISTRIBUTION.value == "distribution"

    def test_reversal_bullish_exists(self):
        assert MidRegime.REVERSAL_BULLISH.value == "reversal_bullish"


class TestMacroRegime:
    def test_has_all_9_macro_regimes(self):
        assert len(MacroRegime) == 9

    def test_bull_euphoria_exists(self):
        assert MacroRegime.MACRO_BULL_EUPHORIA.value == "macro_bull_euphoria"

    def test_bear_panic_exists(self):
        assert MacroRegime.MACRO_BEAR_PANIC.value == "macro_bear_panic"

    def test_uncertain_exists(self):
        assert MacroRegime.MACRO_UNCERTAIN.value == "macro_uncertain"


class TestSynthesizedRegime:
    def test_has_all_19_synthesized_regimes(self):
        assert len(SynthesizedRegime) == 19

    def test_strong_bull_exists(self):
        assert SynthesizedRegime.REGIME_STRONG_BULL.value == "strong_bull"

    def test_panic_exists(self):
        assert SynthesizedRegime.REGIME_PANIC.value == "panic"

    def test_uncertain_exists(self):
        assert SynthesizedRegime.REGIME_UNCERTAIN.value == "uncertain"

    def test_all_regime_values_unique(self):
        values = [r.value for r in SynthesizedRegime]
        assert len(values) == len(set(values))


class TestCompositeRegime:
    @pytest.fixture
    def sample_regime(self):
        return CompositeRegime(
            micro=MicroRegime.MICRO_TRENDING_UP,
            mid=MidRegime.TREND_BULL_STRONG,
            macro=MacroRegime.MACRO_BULL_HEALTHY,
            synthesized=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=92,
            duration_candles=47,
            transition_probability=0.12,
            recommended_strategies=["TrendFollowing", "MomentumBreakout"],
            risk_multiplier=1.2,
            max_position_size=1.0,
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )

    def test_creation(self, sample_regime):
        assert sample_regime.confidence == 92
        assert sample_regime.synthesized == SynthesizedRegime.REGIME_STRONG_BULL

    def test_is_frozen(self, sample_regime):
        with pytest.raises(FrozenInstanceError):
            sample_regime.confidence = 50

    def test_recommended_strategies(self, sample_regime):
        assert "TrendFollowing" in sample_regime.recommended_strategies

    def test_is_bullish(self, sample_regime):
        assert sample_regime.is_bullish is True

    def test_is_bearish(self):
        regime = CompositeRegime(
            micro=MicroRegime.MICRO_TRENDING_DOWN,
            mid=MidRegime.TREND_BEAR_STRONG,
            macro=MacroRegime.MACRO_BEAR_PANIC,
            synthesized=SynthesizedRegime.REGIME_PANIC,
            confidence=85,
            duration_candles=10,
            transition_probability=0.05,
            recommended_strategies=[],
            risk_multiplier=0.3,
            max_position_size=0.2,
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        assert regime.is_bearish is True
        assert regime.is_bullish is False

    def test_is_high_confidence(self, sample_regime):
        assert sample_regime.is_high_confidence is True

    def test_is_low_confidence(self):
        regime = CompositeRegime(
            micro=MicroRegime.MICRO_CHOPPY,
            mid=MidRegime.RANGING_TIGHT,
            macro=MacroRegime.MACRO_UNCERTAIN,
            synthesized=SynthesizedRegime.REGIME_UNCERTAIN,
            confidence=35,
            duration_candles=3,
            transition_probability=0.5,
            recommended_strategies=[],
            risk_multiplier=0.5,
            max_position_size=0.3,
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        assert regime.is_high_confidence is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/home/atabey/Belgeler/Snake oyunu/claude"
python -m pytest nexus_strategy/tests/domain/test_models/test_regime.py -v
```
Expected: FAIL - ImportError (module doesn't exist yet)

- [ ] **Step 3: Implement regime models**

`nexus_strategy/domain/models/regime.py`:
```python
"""Regime detection model definitions.

Defines the 3-layer regime hierarchy:
- MicroRegime: Fast regime from 5m-15m analysis (8 states)
- MidRegime: Mid regime from 1h-4h analysis (10 states)
- MacroRegime: Macro regime from 1d + Sentinel (9 states)
- SynthesizedRegime: Final combined regime (19 states)
- CompositeRegime: Frozen dataclass combining all layers with metadata

Part of the DOMAIN layer - zero external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MicroRegime(Enum):
    """Fast regime states detected from 5m-15m timeframe analysis."""
    MICRO_TRENDING_UP = "micro_trending_up"
    MICRO_TRENDING_DOWN = "micro_trending_down"
    MICRO_RANGING = "micro_ranging"
    MICRO_VOLATILE = "micro_volatile"
    MICRO_SQUEEZE = "micro_squeeze"
    MICRO_BREAKOUT_UP = "micro_breakout_up"
    MICRO_BREAKOUT_DOWN = "micro_breakout_down"
    MICRO_CHOPPY = "micro_choppy"


class MidRegime(Enum):
    """Mid-term regime states detected from 1h-4h timeframe analysis."""
    TREND_BULL_STRONG = "trend_bull_strong"
    TREND_BULL_WEAK = "trend_bull_weak"
    TREND_BEAR_STRONG = "trend_bear_strong"
    TREND_BEAR_WEAK = "trend_bear_weak"
    RANGING_TIGHT = "ranging_tight"
    RANGING_WIDE = "ranging_wide"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    REVERSAL_BULLISH = "reversal_bullish"
    REVERSAL_BEARISH = "reversal_bearish"


class MacroRegime(Enum):
    """Macro regime states detected from 1d timeframe + Sentinel data."""
    MACRO_BULL_EUPHORIA = "macro_bull_euphoria"
    MACRO_BULL_HEALTHY = "macro_bull_healthy"
    MACRO_BULL_EARLY = "macro_bull_early"
    MACRO_BEAR_PANIC = "macro_bear_panic"
    MACRO_BEAR_GRIND = "macro_bear_grind"
    MACRO_BEAR_EARLY = "macro_bear_early"
    MACRO_TRANSITION_UP = "macro_transition_up"
    MACRO_TRANSITION_DOWN = "macro_transition_down"
    MACRO_UNCERTAIN = "macro_uncertain"


class SynthesizedRegime(Enum):
    """Final synthesized regime combining all 3 layers into actionable states."""
    REGIME_STRONG_BULL = "strong_bull"
    REGIME_MODERATE_BULL = "moderate_bull"
    REGIME_WEAK_BULL = "weak_bull"
    REGIME_STRONG_BEAR = "strong_bear"
    REGIME_MODERATE_BEAR = "moderate_bear"
    REGIME_WEAK_BEAR = "weak_bear"
    REGIME_RANGING_TIGHT = "ranging_tight"
    REGIME_RANGING_WIDE = "ranging_wide"
    REGIME_SQUEEZE = "squeeze"
    REGIME_BREAKOUT_BULL = "breakout_bull"
    REGIME_BREAKOUT_BEAR = "breakout_bear"
    REGIME_ACCUMULATION = "accumulation"
    REGIME_DISTRIBUTION = "distribution"
    REGIME_TRANSITION_UP = "transition_up"
    REGIME_TRANSITION_DOWN = "transition_down"
    REGIME_EUPHORIA = "euphoria"
    REGIME_PANIC = "panic"
    REGIME_CHOPPY = "choppy"
    REGIME_UNCERTAIN = "uncertain"


_BULLISH_REGIMES = frozenset({
    SynthesizedRegime.REGIME_STRONG_BULL,
    SynthesizedRegime.REGIME_MODERATE_BULL,
    SynthesizedRegime.REGIME_WEAK_BULL,
    SynthesizedRegime.REGIME_BREAKOUT_BULL,
    SynthesizedRegime.REGIME_ACCUMULATION,
    SynthesizedRegime.REGIME_TRANSITION_UP,
    SynthesizedRegime.REGIME_EUPHORIA,
})

_BEARISH_REGIMES = frozenset({
    SynthesizedRegime.REGIME_STRONG_BEAR,
    SynthesizedRegime.REGIME_MODERATE_BEAR,
    SynthesizedRegime.REGIME_WEAK_BEAR,
    SynthesizedRegime.REGIME_BREAKOUT_BEAR,
    SynthesizedRegime.REGIME_DISTRIBUTION,
    SynthesizedRegime.REGIME_TRANSITION_DOWN,
    SynthesizedRegime.REGIME_PANIC,
})


@dataclass(frozen=True)
class CompositeRegime:
    """Immutable composite regime state combining all 3 detection layers."""
    micro: MicroRegime
    mid: MidRegime
    macro: MacroRegime
    synthesized: SynthesizedRegime
    confidence: int  # 0-100
    duration_candles: int
    transition_probability: float  # 0.0-1.0
    recommended_strategies: list[str]
    risk_multiplier: float
    max_position_size: float
    timestamp: datetime

    @property
    def is_bullish(self) -> bool:
        return self.synthesized in _BULLISH_REGIMES

    @property
    def is_bearish(self) -> bool:
        return self.synthesized in _BEARISH_REGIMES

    @property
    def is_neutral(self) -> bool:
        return not self.is_bullish and not self.is_bearish

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 70
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_regime.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/domain/models/regime.py nexus_strategy/tests/domain/test_models/test_regime.py
git commit -m "feat: add regime model definitions with 4 enum types and CompositeRegime"
```

---

### Task 3: Signal Models

**Files:**
- Create: `nexus_strategy/domain/models/signal.py`
- Test: `nexus_strategy/tests/domain/test_models/test_signal.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/domain/test_models/test_signal.py`:
```python
"""Tests for signal model definitions."""
import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from nexus_strategy.domain.models.signal import (
    Signal,
    ExitSignal,
    SignalBundle,
    ExitLayer,
)


class TestSignal:
    @pytest.fixture
    def sample_signal(self):
        return Signal(
            pair="ETH/USDT",
            strategy_name="mean_reversion",
            action="BUY",
            confidence=78,
            entry_price=3200.50,
            stop_loss=3040.48,
            take_profit_levels=[
                {"price": 3360.53, "pct_to_sell": 0.25},
                {"price": 3520.55, "pct_to_sell": 0.25},
                {"price": 3680.58, "pct_to_sell": 0.50},
            ],
            indicators_used=["RSI_14", "BB_20_2.0", "StochRSI_K"],
            reasoning="RSI oversold at 22, price below BB lower, StochRSI bottoming",
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )

    def test_creation(self, sample_signal):
        assert sample_signal.pair == "ETH/USDT"
        assert sample_signal.confidence == 78

    def test_is_frozen(self, sample_signal):
        with pytest.raises(FrozenInstanceError):
            sample_signal.confidence = 50

    def test_is_buy(self, sample_signal):
        assert sample_signal.is_buy is True

    def test_no_signal(self):
        sig = Signal(
            pair="BTC/USDT",
            strategy_name="trend_following",
            action="NO_SIGNAL",
            confidence=0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit_levels=[],
            indicators_used=[],
            reasoning="No trend detected",
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        assert sig.is_buy is False

    def test_stop_loss_pct(self, sample_signal):
        expected = (3040.48 - 3200.50) / 3200.50
        assert abs(sample_signal.stop_loss_pct - expected) < 0.0001


class TestExitSignal:
    def test_creation(self):
        sig = ExitSignal(
            should_exit=True,
            urgency=85,
            exit_layer=ExitLayer.TECHNICAL,
            partial_pct=0.5,
            reason="Bearish divergence on RSI + MACD",
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        assert sig.should_exit is True
        assert sig.urgency == 85
        assert sig.exit_layer == ExitLayer.TECHNICAL

    def test_is_frozen(self):
        sig = ExitSignal(
            should_exit=False,
            urgency=0,
            exit_layer=ExitLayer.EMERGENCY,
            partial_pct=0.0,
            reason="No exit needed",
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            sig.should_exit = True


class TestExitLayer:
    def test_has_5_layers(self):
        assert len(ExitLayer) == 5

    def test_priority_order(self):
        assert ExitLayer.EMERGENCY.value < ExitLayer.TECHNICAL.value
        assert ExitLayer.TECHNICAL.value < ExitLayer.REGIME.value
        assert ExitLayer.REGIME.value < ExitLayer.PORTFOLIO.value
        assert ExitLayer.PORTFOLIO.value < ExitLayer.PROFIT_OPTIMIZER.value


class TestSignalBundle:
    @pytest.fixture
    def sample_bundle(self):
        return SignalBundle(
            action="BUY",
            pair="ETH/USDT",
            composite_score=74,
            consensus_count=4,
            consensus_total=7,
            source_signals=[],
            regime=None,
            suggested_stake_multiplier=0.85,
            weighted_stop_loss=-0.054,
            merged_take_profits=[
                {"price": 3360.0, "pct_to_sell": 0.25},
            ],
            risk_rating="MODERATE",
            reasoning="4/7 strategies approved",
            sentinel_context={"risk_score": 42, "mode": "NORMAL"},
            expiry_candles=3,
            created_at=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )

    def test_creation(self, sample_bundle):
        assert sample_bundle.composite_score == 74

    def test_is_strong_buy(self, sample_bundle):
        assert sample_bundle.is_strong_buy is True

    def test_is_buy(self, sample_bundle):
        assert sample_bundle.is_buy is True

    def test_is_rejected(self):
        bundle = SignalBundle(
            action="REJECT",
            pair="DOGE/USDT",
            composite_score=38,
            consensus_count=1,
            consensus_total=7,
            source_signals=[],
            regime=None,
            suggested_stake_multiplier=0.0,
            weighted_stop_loss=0.0,
            merged_take_profits=[],
            risk_rating="HIGH",
            reasoning="Insufficient consensus",
            sentinel_context={},
            expiry_candles=0,
            created_at=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )
        assert bundle.is_buy is False
        assert bundle.is_rejected is True

    def test_consensus_ratio(self, sample_bundle):
        assert sample_bundle.consensus_ratio == 4 / 7

    def test_is_frozen(self, sample_bundle):
        with pytest.raises(FrozenInstanceError):
            sample_bundle.composite_score = 90
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_signal.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement signal models**

`nexus_strategy/domain/models/signal.py`:
```python
"""Signal model definitions for the Nexus strategy.

Part of the DOMAIN layer - zero external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any


class ExitLayer(IntEnum):
    """Exit engine layers in priority order (lower = higher priority)."""
    EMERGENCY = 1
    TECHNICAL = 2
    REGIME = 3
    PORTFOLIO = 4
    PROFIT_OPTIMIZER = 5


@dataclass(frozen=True)
class Signal:
    """Individual sub-strategy entry signal."""
    pair: str
    strategy_name: str
    action: str  # "BUY" or "NO_SIGNAL"
    confidence: int  # 0-100
    entry_price: float
    stop_loss: float
    take_profit_levels: list[dict[str, float]]
    indicators_used: list[str]
    reasoning: str
    timestamp: datetime

    @property
    def is_buy(self) -> bool:
        return self.action == "BUY" and self.confidence > 0

    @property
    def stop_loss_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.stop_loss - self.entry_price) / self.entry_price


@dataclass(frozen=True)
class ExitSignal:
    """Exit recommendation from any exit engine layer."""
    should_exit: bool
    urgency: int  # 0-100
    exit_layer: ExitLayer
    partial_pct: float  # 0.0-1.0
    reason: str
    timestamp: datetime


@dataclass(frozen=True)
class SignalBundle:
    """Meta-strategy fusion result - the final trading decision."""
    action: str  # "BUY" or "REJECT"
    pair: str
    composite_score: int  # 0-100
    consensus_count: int
    consensus_total: int
    source_signals: list[Any]
    regime: Any  # CompositeRegime
    suggested_stake_multiplier: float
    weighted_stop_loss: float
    merged_take_profits: list[dict[str, float]]
    risk_rating: str  # "LOW", "MODERATE", "HIGH"
    reasoning: str
    sentinel_context: dict[str, Any]
    expiry_candles: int
    created_at: datetime

    @property
    def is_buy(self) -> bool:
        return self.action == "BUY"

    @property
    def is_rejected(self) -> bool:
        return self.action == "REJECT"

    @property
    def is_strong_buy(self) -> bool:
        return self.is_buy and self.composite_score >= 70

    @property
    def consensus_ratio(self) -> float:
        if self.consensus_total == 0:
            return 0.0
        return self.consensus_count / self.consensus_total
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_signal.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/domain/models/signal.py nexus_strategy/tests/domain/test_models/test_signal.py
git commit -m "feat: add signal model definitions with Signal, ExitSignal, SignalBundle"
```

---

## Chunk 2: Risk/Trade Models, MarketState, Port Interfaces

### Task 4: Risk and Trade Context Models

**Files:**
- Create: `nexus_strategy/domain/models/risk.py`
- Create: `nexus_strategy/domain/models/trade_context.py`
- Test: `nexus_strategy/tests/domain/test_models/test_risk.py`
- Test: `nexus_strategy/tests/domain/test_models/test_trade_context.py`

- [ ] **Step 1: Write failing tests for risk models**

`nexus_strategy/tests/domain/test_models/test_risk.py`:
```python
"""Tests for risk model definitions."""
import pytest

from nexus_strategy.domain.models.risk import (
    PortfolioState,
    PositionAction,
    DrawdownLevel,
)


class TestDrawdownLevel:
    def test_has_5_levels(self):
        assert len(DrawdownLevel) == 5

    def test_from_drawdown_normal(self):
        assert DrawdownLevel.from_drawdown(0.03) == DrawdownLevel.NORMAL

    def test_from_drawdown_caution(self):
        assert DrawdownLevel.from_drawdown(0.07) == DrawdownLevel.CAUTION

    def test_from_drawdown_warning(self):
        assert DrawdownLevel.from_drawdown(0.12) == DrawdownLevel.WARNING

    def test_from_drawdown_critical(self):
        assert DrawdownLevel.from_drawdown(0.18) == DrawdownLevel.CRITICAL

    def test_from_drawdown_catastrophic(self):
        assert DrawdownLevel.from_drawdown(0.25) == DrawdownLevel.CATASTROPHIC


class TestPositionAction:
    def test_hold_action(self):
        action = PositionAction(action="HOLD", amount=0.0, reason="All good", urgency=0)
        assert action.action == "HOLD"

    def test_dca_action(self):
        action = PositionAction(action="DCA", amount=50.0, reason="Support hold", urgency=40)
        assert action.amount == 50.0

    def test_derisk_action(self):
        action = PositionAction(action="DERISK", amount=100.0, reason="Regime shift", urgency=70)
        assert action.action == "DERISK"


class TestPortfolioState:
    def test_creation(self):
        state = PortfolioState(
            total_equity=10000.0,
            peak_equity=10500.0,
            current_drawdown=0.0476,
            drawdown_level=DrawdownLevel.NORMAL,
            open_positions=[],
            total_exposure=0.65,
            cash_available=3500.0,
            var_95=0.06,
            cvar_95=0.09,
            correlation_matrix={},
            sector_distribution={},
            recovery_mode=False,
            recovery_progress=0.0,
        )
        assert state.total_equity == 10000.0
        assert state.drawdown_level == DrawdownLevel.NORMAL

    def test_exposure_ratio(self):
        state = PortfolioState(
            total_equity=10000.0,
            peak_equity=10000.0,
            current_drawdown=0.0,
            drawdown_level=DrawdownLevel.NORMAL,
            open_positions=[],
            total_exposure=6500.0,
            cash_available=3500.0,
            var_95=0.06,
            cvar_95=0.09,
            correlation_matrix={},
            sector_distribution={},
            recovery_mode=False,
            recovery_progress=0.0,
        )
        assert state.exposure_ratio == 0.65
```

- [ ] **Step 2: Write failing tests for trade context**

`nexus_strategy/tests/domain/test_models/test_trade_context.py`:
```python
"""Tests for trade context model."""
import pytest
from datetime import datetime, timezone

from nexus_strategy.domain.models.trade_context import TradeContext


class TestTradeContext:
    @pytest.fixture
    def sample_context(self):
        return TradeContext(
            trade_id="nexus_2026_0001",
            pair="ETH/USDT",
            entry_signal=None,
            entry_regime=None,
            entry_timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
            entry_price=3200.0,
            current_avg_price=3200.0,
            total_stake=100.0,
            dca_count=0,
            dca_history=[],
            derisk_count=0,
            derisk_history=[],
            partial_tp_history=[],
            max_profit_reached=0.02,
            max_loss_reached=-0.01,
            current_pnl=0.015,
            position_score=75.0,
            time_in_trade_candles=10,
            regime_changes=[],
            trailing_stop_price=3040.0,
            current_trailing_distance=0.05,
            last_validation={"status": "confirmed"},
            strategy_confidence_now=72.0,
        )

    def test_creation(self, sample_context):
        assert sample_context.pair == "ETH/USDT"
        assert sample_context.dca_count == 0

    def test_is_profitable(self, sample_context):
        assert sample_context.is_profitable is True

    def test_is_in_loss(self):
        ctx = TradeContext(
            trade_id="nexus_2026_0002",
            pair="BTC/USDT",
            entry_signal=None,
            entry_regime=None,
            entry_timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
            entry_price=65000.0,
            current_avg_price=65000.0,
            total_stake=200.0,
            dca_count=0,
            dca_history=[],
            derisk_count=0,
            derisk_history=[],
            partial_tp_history=[],
            max_profit_reached=0.0,
            max_loss_reached=-0.05,
            current_pnl=-0.03,
            position_score=40.0,
            time_in_trade_candles=50,
            regime_changes=[],
            trailing_stop_price=61750.0,
            current_trailing_distance=0.05,
            last_validation={"status": "flagged"},
            strategy_confidence_now=30.0,
        )
        assert ctx.is_profitable is False

    def test_to_custom_data(self, sample_context):
        data = sample_context.to_custom_data()
        assert isinstance(data, dict)
        assert data["trade_id"] == "nexus_2026_0001"
        assert data["dca_count"] == 0

    def test_from_custom_data(self, sample_context):
        data = sample_context.to_custom_data()
        restored = TradeContext.from_custom_data(data)
        assert restored.trade_id == sample_context.trade_id
        assert restored.pair == sample_context.pair
        assert restored.entry_price == sample_context.entry_price
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_risk.py nexus_strategy/tests/domain/test_models/test_trade_context.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 4: Implement risk models**

`nexus_strategy/domain/models/risk.py`:
```python
"""Risk management model definitions.

Part of the DOMAIN layer - zero external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class DrawdownLevel(IntEnum):
    """Portfolio drawdown severity levels."""
    NORMAL = 1      # dd < 5%
    CAUTION = 2     # dd 5-10%
    WARNING = 3     # dd 10-15%
    CRITICAL = 4    # dd 15-20%
    CATASTROPHIC = 5  # dd > 20%

    @classmethod
    def from_drawdown(cls, dd: float) -> DrawdownLevel:
        if dd < 0.05:
            return cls.NORMAL
        elif dd < 0.10:
            return cls.CAUTION
        elif dd < 0.15:
            return cls.WARNING
        elif dd < 0.20:
            return cls.CRITICAL
        else:
            return cls.CATASTROPHIC


@dataclass
class PositionAction:
    """Decision output for position management."""
    action: str  # HOLD, DCA, DERISK, CLOSE, TRAIL_TIGHTEN
    amount: float
    reason: str
    urgency: int  # 0-100


@dataclass
class PortfolioState:
    """Current state of the entire portfolio."""
    total_equity: float
    peak_equity: float
    current_drawdown: float
    drawdown_level: DrawdownLevel
    open_positions: list[dict[str, Any]]
    total_exposure: float
    cash_available: float
    var_95: float
    cvar_95: float
    correlation_matrix: dict[str, dict[str, float]]
    sector_distribution: dict[str, float]
    recovery_mode: bool
    recovery_progress: float

    @property
    def exposure_ratio(self) -> float:
        if self.total_equity == 0:
            return 0.0
        return self.total_exposure / self.total_equity
```

- [ ] **Step 5: Implement trade context model**

`nexus_strategy/domain/models/trade_context.py`:
```python
"""Trade context model for tracking rich per-position state.

Part of the DOMAIN layer - zero external dependencies.
Serialization to/from dict is pure (no Freqtrade import).
The Freqtrade adapter handles set_custom_data()/get_custom_data().
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TradeContext:
    """Rich context for each open position."""
    trade_id: str
    pair: str
    entry_signal: Any
    entry_regime: Any
    entry_timestamp: datetime
    entry_price: float
    current_avg_price: float
    total_stake: float

    dca_count: int
    dca_history: list[dict[str, Any]]
    derisk_count: int
    derisk_history: list[dict[str, Any]]
    partial_tp_history: list[dict[str, Any]]

    max_profit_reached: float
    max_loss_reached: float
    current_pnl: float

    position_score: float
    time_in_trade_candles: int
    regime_changes: list[dict[str, Any]]

    trailing_stop_price: float
    current_trailing_distance: float

    last_validation: dict[str, Any]
    strategy_confidence_now: float

    @property
    def is_profitable(self) -> bool:
        return self.current_pnl > 0

    def to_custom_data(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict (pure, no framework dependency)."""
        data = {}
        for k, v in self.__dict__.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            elif v is None or isinstance(v, (str, int, float, bool, list, dict)):
                data[k] = v
            else:
                data[k] = None
        return data

    @classmethod
    def from_custom_data(cls, data: dict[str, Any]) -> TradeContext:
        """Deserialize from dict (pure, no framework dependency)."""
        parsed = dict(data)
        if isinstance(parsed.get("entry_timestamp"), str):
            parsed["entry_timestamp"] = datetime.fromisoformat(parsed["entry_timestamp"])
        return cls(**parsed)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_risk.py nexus_strategy/tests/domain/test_models/test_trade_context.py -v
```
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add nexus_strategy/domain/models/risk.py nexus_strategy/domain/models/trade_context.py nexus_strategy/tests/domain/test_models/test_risk.py nexus_strategy/tests/domain/test_models/test_trade_context.py
git commit -m "feat: add risk and trade context models"
```

---

### Task 5: MarketState Model

**Files:**
- Create: `nexus_strategy/domain/models/market_state.py`
- Modify: `nexus_strategy/domain/models/__init__.py`
- Test: `nexus_strategy/tests/domain/test_models/test_market_state.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/domain/test_models/test_market_state.py`:
```python
"""Tests for MarketState frozen snapshot."""
import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    MicroRegime, MidRegime, MacroRegime, SynthesizedRegime, CompositeRegime,
)


class TestMarketState:
    @pytest.fixture
    def sample_regime(self):
        return CompositeRegime(
            micro=MicroRegime.MICRO_TRENDING_UP,
            mid=MidRegime.TREND_BULL_STRONG,
            macro=MacroRegime.MACRO_BULL_HEALTHY,
            synthesized=SynthesizedRegime.REGIME_STRONG_BULL,
            confidence=92,
            duration_candles=47,
            transition_probability=0.12,
            recommended_strategies=["TrendFollowing"],
            risk_multiplier=1.2,
            max_position_size=1.0,
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
        )

    @pytest.fixture
    def sample_state(self, sample_regime):
        return MarketState(
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
            indicators={"ETH/USDT": {"5m": {"RSI_14": 45.0}}},
            composite_indicators={"ETH/USDT": {"composite_rsi": 42.0}},
            regime=sample_regime,
            previous_regime=sample_regime,
            regime_just_changed=False,
            sentinel={"risk_score": 42, "mode": "NORMAL"},
            sentinel_connected=True,
            sentinel_data_age_seconds=2,
            btc_price=65000.0,
            btc_change_1h=-0.5,
            btc_change_24h=2.1,
            btc_above_ema200=True,
            btc_trend="BULLISH",
            market_phase="ALT_RALLY",
            altcoin_season_index=68,
            fear_greed=62,
            indicator_weights={"RSI_14": 1.2, "EMA_200": 1.0},
            strategy_weights={"mean_reversion": {"strong_bull": 0.5}},
            indicator_reliability={"RSI_14": 0.78},
        )

    def test_creation(self, sample_state):
        assert sample_state.btc_price == 65000.0

    def test_is_frozen(self, sample_state):
        with pytest.raises(FrozenInstanceError):
            sample_state.btc_price = 70000.0

    def test_sentinel_is_stale_false(self, sample_state):
        assert sample_state.sentinel_is_stale is False

    def test_sentinel_is_stale_true(self, sample_regime):
        state = MarketState(
            timestamp=datetime(2026, 3, 11, 14, 35, tzinfo=timezone.utc),
            indicators={},
            composite_indicators={},
            regime=sample_regime,
            previous_regime=sample_regime,
            regime_just_changed=False,
            sentinel={},
            sentinel_connected=True,
            sentinel_data_age_seconds=600,
            btc_price=65000.0,
            btc_change_1h=0.0,
            btc_change_24h=0.0,
            btc_above_ema200=True,
            btc_trend="NEUTRAL",
            market_phase="MIXED",
            altcoin_season_index=50,
            fear_greed=50,
            indicator_weights={},
            strategy_weights={},
            indicator_reliability={},
        )
        assert state.sentinel_is_stale is True

    def test_get_indicator(self, sample_state):
        val = sample_state.get_indicator("ETH/USDT", "5m", "RSI_14")
        assert val == 45.0

    def test_get_indicator_missing(self, sample_state):
        val = sample_state.get_indicator("BTC/USDT", "5m", "RSI_14")
        assert val is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/test_market_state.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement MarketState**

`nexus_strategy/domain/models/market_state.py`:
```python
"""MarketState - Immutable snapshot of all market data.

Part of the DOMAIN layer - only imports from domain.models.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nexus_strategy.domain.models.regime import CompositeRegime

SENTINEL_STALE_THRESHOLD_SECONDS = 300  # 5 minutes


@dataclass(frozen=True)
class MarketState:
    """Immutable market snapshot produced by DataLayer every candle."""
    timestamp: datetime

    # Indicator data
    indicators: dict[str, dict[str, dict[str, float]]]
    composite_indicators: dict[str, dict[str, float]]

    # Regime state
    regime: CompositeRegime
    previous_regime: CompositeRegime
    regime_just_changed: bool

    # Sentinel data
    sentinel: dict[str, Any]
    sentinel_connected: bool
    sentinel_data_age_seconds: int

    # BTC state
    btc_price: float
    btc_change_1h: float
    btc_change_24h: float
    btc_above_ema200: bool
    btc_trend: str

    # Market overview
    market_phase: str
    altcoin_season_index: int
    fear_greed: int

    # Intelligence layer weights
    indicator_weights: dict[str, float]
    strategy_weights: dict[str, dict[str, float]]
    indicator_reliability: dict[str, float]

    @property
    def sentinel_is_stale(self) -> bool:
        return self.sentinel_data_age_seconds > SENTINEL_STALE_THRESHOLD_SECONDS

    def get_indicator(self, pair: str, timeframe: str, indicator: str) -> float | None:
        try:
            return self.indicators[pair][timeframe][indicator]
        except KeyError:
            return None
```

- [ ] **Step 4: Create domain models __init__.py with re-exports**

`nexus_strategy/domain/models/__init__.py`:
```python
"""Domain models - all immutable data structures."""
from nexus_strategy.domain.models.regime import (
    MicroRegime, MidRegime, MacroRegime, SynthesizedRegime, CompositeRegime,
)
from nexus_strategy.domain.models.signal import Signal, ExitSignal, SignalBundle, ExitLayer
from nexus_strategy.domain.models.risk import PortfolioState, PositionAction, DrawdownLevel
from nexus_strategy.domain.models.trade_context import TradeContext
from nexus_strategy.domain.models.market_state import MarketState

__all__ = [
    "MicroRegime", "MidRegime", "MacroRegime", "SynthesizedRegime", "CompositeRegime",
    "Signal", "ExitSignal", "SignalBundle", "ExitLayer",
    "PortfolioState", "PositionAction", "DrawdownLevel",
    "TradeContext",
    "MarketState",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/domain/test_models/ -v
```
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add nexus_strategy/domain/models/
git commit -m "feat: add MarketState model and domain models __init__"
```

---

### Task 6: Port Interfaces (Hexagonal Architecture Core)

**Files:**
- Create: `nexus_strategy/domain/ports/data_port.py`
- Create: `nexus_strategy/domain/ports/sentinel_port.py`
- Create: `nexus_strategy/domain/ports/config_port.py`
- Create: `nexus_strategy/domain/ports/storage_port.py`
- Create: `nexus_strategy/domain/ports/analytics_port.py`
- Create: `nexus_strategy/domain/ports/trade_repo_port.py`
- Create: `nexus_strategy/domain/ports/__init__.py`
- Test: `nexus_strategy/tests/domain/test_ports/test_port_contracts.py`

- [ ] **Step 1: Write failing tests for port contracts**

`nexus_strategy/tests/domain/test_ports/test_port_contracts.py`:
```python
"""Tests that port interfaces are proper ABCs and cannot be instantiated."""
import pytest
from abc import ABC

from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository


class TestPortsAreAbstract:
    """All ports must be ABCs that cannot be directly instantiated."""

    def test_data_provider_is_abc(self):
        assert issubclass(IDataProvider, ABC)
        with pytest.raises(TypeError):
            IDataProvider()

    def test_indicator_engine_is_abc(self):
        assert issubclass(IIndicatorEngine, ABC)
        with pytest.raises(TypeError):
            IIndicatorEngine()

    def test_sentinel_provider_is_abc(self):
        assert issubclass(ISentinelProvider, ABC)
        with pytest.raises(TypeError):
            ISentinelProvider()

    def test_config_provider_is_abc(self):
        assert issubclass(IConfigProvider, ABC)
        with pytest.raises(TypeError):
            IConfigProvider()

    def test_storage_provider_is_abc(self):
        assert issubclass(IStorageProvider, ABC)
        with pytest.raises(TypeError):
            IStorageProvider()

    def test_analytics_emitter_is_abc(self):
        assert issubclass(IAnalyticsEmitter, ABC)
        with pytest.raises(TypeError):
            IAnalyticsEmitter()

    def test_trade_repository_is_abc(self):
        assert issubclass(ITradeRepository, ABC)
        with pytest.raises(TypeError):
            ITradeRepository()


class TestPortMethodSignatures:
    """Verify ports define the expected abstract methods."""

    def test_data_provider_has_get_market_state(self):
        assert hasattr(IDataProvider, "get_market_state")

    def test_data_provider_has_get_candles(self):
        assert hasattr(IDataProvider, "get_candles")

    def test_sentinel_provider_has_get_sentinel_data(self):
        assert hasattr(ISentinelProvider, "get_sentinel_data")

    def test_sentinel_provider_has_is_connected(self):
        assert hasattr(ISentinelProvider, "is_connected")

    def test_config_provider_has_get(self):
        assert hasattr(IConfigProvider, "get")

    def test_config_provider_has_get_profile(self):
        assert hasattr(IConfigProvider, "get_profile")

    def test_storage_provider_has_save(self):
        assert hasattr(IStorageProvider, "save")

    def test_storage_provider_has_load(self):
        assert hasattr(IStorageProvider, "load")

    def test_analytics_emitter_has_emit(self):
        assert hasattr(IAnalyticsEmitter, "emit_metric")

    def test_analytics_emitter_has_log_decision(self):
        assert hasattr(IAnalyticsEmitter, "log_decision")

    def test_trade_repository_has_save_context(self):
        assert hasattr(ITradeRepository, "save_context")

    def test_trade_repository_has_load_context(self):
        assert hasattr(ITradeRepository, "load_context")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/domain/test_ports/test_port_contracts.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement port interfaces**

`nexus_strategy/domain/ports/data_port.py`:
```python
"""Data access port interfaces.

These ABCs define how the domain accesses market data.
Adapters (Freqtrade, backtest, mock) implement these.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from nexus_strategy.domain.models.market_state import MarketState


class IDataProvider(ABC):
    """Port for accessing market data."""

    @abstractmethod
    def get_market_state(self, pair: str, timeframe: str) -> MarketState:
        """Build a complete MarketState snapshot for current candle."""
        ...

    @abstractmethod
    def get_candles(
        self, pair: str, timeframe: str, count: int
    ) -> dict[str, np.ndarray]:
        """Get OHLCV candle data as numpy arrays."""
        ...

    @abstractmethod
    def get_available_pairs(self) -> list[str]:
        """Get list of tradeable pairs."""
        ...


class IIndicatorEngine(ABC):
    """Port for indicator calculation."""

    @abstractmethod
    def calculate(
        self, pair: str, timeframe: str, candles: dict[str, np.ndarray]
    ) -> dict[str, float]:
        """Calculate all indicators for a pair/timeframe."""
        ...

    @abstractmethod
    def get_indicator(
        self, pair: str, timeframe: str, indicator_name: str
    ) -> float | None:
        """Get a single indicator value."""
        ...
```

`nexus_strategy/domain/ports/sentinel_port.py`:
```python
"""Sentinel engine port interface.

Defines how the domain reads real-time external data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ISentinelProvider(ABC):
    """Port for accessing Sentinel Engine data."""

    @abstractmethod
    def get_sentinel_data(self) -> dict[str, Any]:
        """Get latest sentinel command channel data."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if sentinel connection is alive."""
        ...

    @abstractmethod
    def get_risk_score(self) -> int:
        """Get current composite risk score (0-100)."""
        ...

    @abstractmethod
    def get_strategy_mode(self) -> str:
        """Get sentinel-recommended strategy mode."""
        ...

    @abstractmethod
    def get_data_age_seconds(self) -> int:
        """Get age of last sentinel update in seconds."""
        ...
```

`nexus_strategy/domain/ports/config_port.py`:
```python
"""Configuration port interface.

Defines how the domain reads configuration values.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IConfigProvider(ABC):
    """Port for accessing configuration."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key."""
        ...

    @abstractmethod
    def get_profile(self) -> str:
        """Get the active profile name."""
        ...

    @abstractmethod
    def get_strategy_config(self, strategy_name: str) -> dict[str, Any]:
        """Get configuration for a specific sub-strategy."""
        ...

    @abstractmethod
    def get_regime_weights(self, regime_name: str) -> dict[str, float]:
        """Get strategy weights for a specific regime."""
        ...

    @abstractmethod
    def on_config_change(self, callback: Any) -> None:
        """Register callback for configuration hot-reload events."""
        ...
```

`nexus_strategy/domain/ports/storage_port.py`:
```python
"""Storage port interface.

Defines how the domain persists data (analytics, journal, etc).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStorageProvider(ABC):
    """Port for data persistence."""

    @abstractmethod
    def save(self, collection: str, data: dict[str, Any]) -> None:
        """Save a data record to a named collection."""
        ...

    @abstractmethod
    def load(
        self, collection: str, query: dict[str, Any] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Load records from a named collection."""
        ...

    @abstractmethod
    def save_time_series(
        self, metric_name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Save a time-series metric point."""
        ...
```

`nexus_strategy/domain/ports/analytics_port.py`:
```python
"""Analytics and logging port interface.

Defines how the domain emits metrics and logs decisions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IAnalyticsEmitter(ABC):
    """Port for metrics and decision logging."""

    @abstractmethod
    def emit_metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Emit a numeric metric (for Prometheus, etc)."""
        ...

    @abstractmethod
    def log_decision(
        self,
        decision_type: str,
        pair: str,
        details: dict[str, Any],
    ) -> None:
        """Log a trading decision with full context."""
        ...

    @abstractmethod
    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log a system event (regime change, anomaly, etc)."""
        ...
```

`nexus_strategy/domain/ports/trade_repo_port.py`:
```python
"""Trade repository port interface.

Defines how the domain persists and retrieves trade contexts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from nexus_strategy.domain.models.trade_context import TradeContext


class ITradeRepository(ABC):
    """Port for trade context persistence."""

    @abstractmethod
    def save_context(self, trade_id: str, context: TradeContext) -> None:
        """Persist trade context."""
        ...

    @abstractmethod
    def load_context(self, trade_id: str) -> TradeContext | None:
        """Load trade context by trade ID."""
        ...

    @abstractmethod
    def delete_context(self, trade_id: str) -> None:
        """Delete trade context (trade closed)."""
        ...

    @abstractmethod
    def list_active_contexts(self) -> list[TradeContext]:
        """List all active trade contexts."""
        ...
```

`nexus_strategy/domain/ports/__init__.py`:
```python
"""Domain port interfaces - the hexagonal architecture contracts."""
from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository

__all__ = [
    "IDataProvider", "IIndicatorEngine",
    "ISentinelProvider",
    "IConfigProvider",
    "IStorageProvider",
    "IAnalyticsEmitter",
    "ITradeRepository",
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/domain/test_ports/test_port_contracts.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/domain/ports/
git commit -m "feat: add hexagonal port interfaces (6 ABCs)"
```

---

## Chunk 3: Constants and Math Utils

### Task 7: Constants

**Files:**
- Create: `nexus_strategy/utils/constants.py`

- [ ] **Step 1: Implement constants**

`nexus_strategy/utils/constants.py`:
```python
"""System-wide constants.

Pure data - no external dependencies.
"""

# Sector mapping for portfolio diversification
SECTOR_MAP: dict[str, str] = {
    # Layer 1
    "BTC/USDT": "L1", "ETH/USDT": "L1", "SOL/USDT": "L1",
    "ADA/USDT": "L1", "AVAX/USDT": "L1", "DOT/USDT": "L1",
    "NEAR/USDT": "L1", "ATOM/USDT": "L1", "APT/USDT": "L1",
    "SUI/USDT": "L1", "SEI/USDT": "L1", "TIA/USDT": "L1",
    "ICP/USDT": "L1", "FTM/USDT": "L1", "ALGO/USDT": "L1",
    "HBAR/USDT": "L1", "TON/USDT": "L1", "TRX/USDT": "L1",
    # DeFi
    "UNI/USDT": "DEFI", "AAVE/USDT": "DEFI", "MKR/USDT": "DEFI",
    "SNX/USDT": "DEFI", "COMP/USDT": "DEFI", "CRV/USDT": "DEFI",
    "SUSHI/USDT": "DEFI", "1INCH/USDT": "DEFI", "DYDX/USDT": "DEFI",
    "LDO/USDT": "DEFI", "RPL/USDT": "DEFI", "PENDLE/USDT": "DEFI",
    "JUP/USDT": "DEFI",
    # AI
    "FET/USDT": "AI", "RNDR/USDT": "AI", "AGIX/USDT": "AI",
    "OCEAN/USDT": "AI", "TAO/USDT": "AI", "WLD/USDT": "AI",
    "AKT/USDT": "AI", "AR/USDT": "AI",
    # Gaming / Metaverse
    "AXS/USDT": "GAMING", "SAND/USDT": "GAMING", "MANA/USDT": "GAMING",
    "GALA/USDT": "GAMING", "IMX/USDT": "GAMING", "ILV/USDT": "GAMING",
    "RONIN/USDT": "GAMING", "PIXEL/USDT": "GAMING",
    # Layer 2
    "MATIC/USDT": "L2", "OP/USDT": "L2", "ARB/USDT": "L2",
    "STRK/USDT": "L2", "METIS/USDT": "L2", "MANTA/USDT": "L2",
    "ZK/USDT": "L2",
    # Meme
    "DOGE/USDT": "MEME", "SHIB/USDT": "MEME", "PEPE/USDT": "MEME",
    "BONK/USDT": "MEME", "FLOKI/USDT": "MEME", "WIF/USDT": "MEME",
    # Infrastructure
    "LINK/USDT": "INFRA", "GRT/USDT": "INFRA", "FIL/USDT": "INFRA",
    "THETA/USDT": "INFRA", "PYTH/USDT": "INFRA", "TRB/USDT": "INFRA",
    # Privacy
    "XMR/USDT": "PRIVACY", "ZEC/USDT": "PRIVACY",
    # Exchange
    "BNB/USDT": "EXCHANGE", "CRO/USDT": "EXCHANGE", "OKB/USDT": "EXCHANGE",
}

TOP_COINS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
    "AVAX/USDT", "DOT/USDT", "LINK/USDT", "MATIC/USDT", "NEAR/USDT",
    "ATOM/USDT", "UNI/USDT", "APT/USDT", "OP/USDT", "ARB/USDT",
    "SUI/USDT", "SEI/USDT", "TIA/USDT", "FET/USDT", "RNDR/USDT",
]

# System limits
MAX_OPEN_TRADES = 15
MAX_EXPOSURE_PCT = 0.85
MAX_SINGLE_PAIR_PCT = 0.20
MAX_SECTOR_PCT = 0.35
MIN_SECTORS = 3
MAX_CORRELATION = 0.85

# Timeframes
TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]
BASE_TIMEFRAME = "5m"

# Candle counts
CANDLES_PER_HOUR = 12
CANDLES_PER_DAY = 288
HEARTBEAT_INTERVAL = 1  # every candle

# Learning
MIN_TRADES_FOR_LEARNING = 20
MAX_PARAMETER_DRIFT = 0.50
LEARNING_COOLDOWN_CANDLES = 288  # 1 day
BASE_LEARNING_RATE = 0.01
```

- [ ] **Step 2: Commit**

```bash
git add nexus_strategy/utils/constants.py
git commit -m "feat: add system-wide constants"
```

---

### Task 8: Math Utils

**Files:**
- Create: `nexus_strategy/utils/math_utils.py`
- Test: `nexus_strategy/tests/utils/test_math_utils.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/utils/test_math_utils.py`:
```python
"""Tests for math utility functions."""
import pytest
import numpy as np

from nexus_strategy.utils.math_utils import (
    hurst_exponent,
    rolling_sharpe,
    rolling_sortino,
    kelly_criterion,
    z_score,
    parkinson_volatility,
    normalize_to_range,
)


class TestHurstExponent:
    def test_trending_series(self):
        prices = np.cumsum(np.ones(200)) + np.random.normal(0, 0.1, 200)
        h = hurst_exponent(prices)
        assert h > 0.5  # trending

    def test_mean_reverting_series(self):
        np.random.seed(42)
        prices = np.sin(np.linspace(0, 20, 200)) * 10 + 100
        h = hurst_exponent(prices)
        assert h < 0.5  # mean reverting

    def test_short_series_returns_05(self):
        h = hurst_exponent(np.array([1.0, 2.0, 3.0]))
        assert h == 0.5  # not enough data

    def test_returns_between_0_and_1(self):
        np.random.seed(123)
        prices = np.random.lognormal(0, 0.02, 500)
        prices = np.cumprod(prices) * 100
        h = hurst_exponent(prices)
        assert 0.0 <= h <= 1.0


class TestRollingSharpe:
    def test_positive_returns(self):
        returns = np.array([0.01, 0.02, 0.01, 0.03, 0.02, 0.01, 0.02, 0.01])
        sharpe = rolling_sharpe(returns)
        assert sharpe > 0

    def test_negative_returns(self):
        returns = np.array([-0.01, -0.02, -0.01, -0.03, -0.02, -0.01])
        sharpe = rolling_sharpe(returns)
        assert sharpe < 0

    def test_zero_std_returns_zero(self):
        returns = np.array([0.01, 0.01, 0.01, 0.01])
        sharpe = rolling_sharpe(returns)
        assert sharpe == 0.0


class TestRollingSortino:
    def test_positive_returns(self):
        returns = np.array([0.01, 0.02, 0.01, 0.03, 0.02, 0.01])
        sortino = rolling_sortino(returns)
        assert sortino > 0

    def test_all_negative(self):
        returns = np.array([-0.01, -0.02, -0.03, -0.01, -0.02])
        sortino = rolling_sortino(returns)
        assert sortino < 0


class TestKellyCriterion:
    def test_positive_edge(self):
        kelly = kelly_criterion(win_rate=0.6, avg_win=0.03, avg_loss=0.02)
        assert kelly > 0

    def test_no_edge(self):
        kelly = kelly_criterion(win_rate=0.5, avg_win=0.02, avg_loss=0.02)
        assert kelly == pytest.approx(0.0, abs=0.01)

    def test_negative_edge(self):
        kelly = kelly_criterion(win_rate=0.3, avg_win=0.02, avg_loss=0.03)
        assert kelly < 0

    def test_zero_avg_loss_returns_zero(self):
        kelly = kelly_criterion(win_rate=0.6, avg_win=0.03, avg_loss=0.0)
        assert kelly == 0.0


class TestZScore:
    def test_mean_value(self):
        data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        z = z_score(30.0, data)
        assert z == pytest.approx(0.0, abs=0.01)

    def test_above_mean(self):
        data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        z = z_score(50.0, data)
        assert z > 0

    def test_zero_std_returns_zero(self):
        data = np.array([5.0, 5.0, 5.0, 5.0])
        z = z_score(5.0, data)
        assert z == 0.0


class TestParkinsonVolatility:
    def test_basic(self):
        highs = np.array([105.0, 106.0, 107.0, 108.0, 105.0])
        lows = np.array([95.0, 94.0, 93.0, 92.0, 95.0])
        vol = parkinson_volatility(highs, lows)
        assert vol > 0

    def test_no_range_returns_zero(self):
        highs = np.array([100.0, 100.0, 100.0])
        lows = np.array([100.0, 100.0, 100.0])
        vol = parkinson_volatility(highs, lows)
        assert vol == 0.0


class TestNormalizeToRange:
    def test_basic(self):
        assert normalize_to_range(50.0, 0.0, 100.0, 0.0, 1.0) == 0.5

    def test_clamp_above(self):
        assert normalize_to_range(150.0, 0.0, 100.0, 0.0, 1.0) == 1.0

    def test_clamp_below(self):
        assert normalize_to_range(-50.0, 0.0, 100.0, 0.0, 1.0) == 0.0

    def test_same_min_max_returns_mid(self):
        assert normalize_to_range(5.0, 5.0, 5.0, 0.0, 1.0) == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/utils/test_math_utils.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement math utils**

`nexus_strategy/utils/math_utils.py`:
```python
"""Mathematical utility functions.

Pure functions - only depends on numpy.
"""
from __future__ import annotations

import numpy as np


def hurst_exponent(prices: np.ndarray, max_lag: int = 20) -> float:
    """Calculate Hurst exponent using R/S analysis.

    H > 0.5: trending, H < 0.5: mean-reverting, H = 0.5: random walk.
    """
    if len(prices) < max_lag * 2:
        return 0.5

    lags = range(2, max_lag)
    rs_values = []

    for lag in lags:
        rs_lag = []
        for start in range(0, len(prices) - lag, lag):
            segment = prices[start : start + lag]
            returns = np.diff(segment)
            if len(returns) == 0:
                continue
            mean_ret = np.mean(returns)
            cumdev = np.cumsum(returns - mean_ret)
            r = np.max(cumdev) - np.min(cumdev)
            s = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
            if s > 0:
                rs_lag.append(r / s)
        if rs_lag:
            rs_values.append((np.log(lag), np.log(np.mean(rs_lag))))

    if len(rs_values) < 2:
        return 0.5

    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])

    coeffs = np.polyfit(x, y, 1)
    h = float(np.clip(coeffs[0], 0.0, 1.0))
    return h


def rolling_sharpe(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio from returns array."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(288))  # 5m candles per day


def rolling_sortino(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Calculate annualized Sortino ratio from returns array."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float(np.mean(excess) * np.sqrt(288)) if np.mean(excess) != 0 else 0.0
    downside_std = np.std(downside, ddof=1)
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * np.sqrt(288))


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Calculate Kelly criterion fraction.

    Returns optimal fraction of bankroll to risk.
    """
    if avg_loss == 0:
        return 0.0
    win_loss_ratio = avg_win / avg_loss
    kelly = win_rate - (1 - win_rate) / win_loss_ratio
    return float(kelly)


def z_score(value: float, data: np.ndarray) -> float:
    """Calculate z-score of value relative to data distribution."""
    if len(data) < 2:
        return 0.0
    std = np.std(data, ddof=1)
    if std == 0:
        return 0.0
    return float((value - np.mean(data)) / std)


def parkinson_volatility(highs: np.ndarray, lows: np.ndarray) -> float:
    """Calculate Parkinson volatility estimator from high/low prices."""
    if len(highs) == 0 or len(lows) == 0:
        return 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        hl_ratio = np.where(lows > 0, highs / lows, 1.0)
        log_hl = np.log(hl_ratio)
    variance = np.mean(log_hl**2) / (4 * np.log(2))
    return float(np.sqrt(variance))


def normalize_to_range(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float = 0.0,
    out_max: float = 1.0,
) -> float:
    """Normalize a value from input range to output range with clamping."""
    if in_min == in_max:
        return (out_min + out_max) / 2
    clamped = max(in_min, min(in_max, value))
    normalized = (clamped - in_min) / (in_max - in_min)
    return out_min + normalized * (out_max - out_min)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/utils/test_math_utils.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/utils/math_utils.py nexus_strategy/tests/utils/test_math_utils.py
git commit -m "feat: add math utility functions"
```

---

### Task 9: Cache Utility

**Files:**
- Create: `nexus_strategy/utils/cache.py`
- Test: `nexus_strategy/tests/utils/test_cache.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/utils/test_cache.py`:
```python
"""Tests for TimedCache."""
import time
import pytest

from nexus_strategy.utils.cache import TimedCache


class TestTimedCache:
    def test_set_and_get(self):
        cache = TimedCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_returns_default(self):
        cache = TimedCache(max_size=10, ttl_seconds=60)
        assert cache.get("missing") is None
        assert cache.get("missing", "default") == "default"

    def test_ttl_expiration(self):
        cache = TimedCache(max_size=10, ttl_seconds=0.1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        cache = TimedCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_access_refreshes_lru(self):
        cache = TimedCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # refresh "a"
        cache.set("d", 4)  # should evict "b" (oldest untouched)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_clear(self):
        cache = TimedCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        cache.clear()
        assert cache.get("key1") is None

    def test_len(self):
        cache = TimedCache(max_size=10, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_contains(self):
        cache = TimedCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "missing" not in cache
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/utils/test_cache.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement cache**

`nexus_strategy/utils/cache.py`:
```python
"""Time-based LRU cache.

Pure Python - no external dependencies.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TimedCache:
    """LRU cache with time-based expiration."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._store:
            return default
        value, ts = self._store[key]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return default
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._max_size:
            self._store.popitem(last=False)
        self._store[key] = (value, time.monotonic())

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        if key not in self._store:
            return False
        _, ts = self._store[key]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return False
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/utils/test_cache.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/utils/cache.py nexus_strategy/tests/utils/test_cache.py
git commit -m "feat: add TimedCache with LRU eviction"
```

---

### Task 10: Decorators

**Files:**
- Create: `nexus_strategy/utils/decorators.py`
- Test: `nexus_strategy/tests/utils/test_decorators.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/utils/test_decorators.py`:
```python
"""Tests for utility decorators."""
import pytest
import time
import logging

from nexus_strategy.utils.decorators import log_decision, timed


class TestLogDecision:
    def test_logs_function_call(self, caplog):
        @log_decision("test_system")
        def make_decision(pair: str, action: str) -> str:
            return f"{action} {pair}"

        with caplog.at_level(logging.INFO):
            result = make_decision("ETH/USDT", "BUY")

        assert result == "BUY ETH/USDT"
        assert "test_system" in caplog.text

    def test_logs_exception(self, caplog):
        @log_decision("test_system")
        def failing():
            raise ValueError("test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                failing()

        assert "test error" in caplog.text


class TestTimed:
    def test_measures_time(self, caplog):
        @timed("test_op")
        def slow_function():
            time.sleep(0.05)
            return 42

        with caplog.at_level(logging.DEBUG):
            result = slow_function()

        assert result == 42
        assert "test_op" in caplog.text

    def test_preserves_return_value(self):
        @timed("test")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/utils/test_decorators.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement decorators**

`nexus_strategy/utils/decorators.py`:
```python
"""Utility decorators for logging and timing.

Uses stdlib logging - no external dependencies.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("nexus")


def log_decision(subsystem: str) -> Callable:
    """Decorator that logs function calls with subsystem context."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info(
                "[%s] %s called | args=%s kwargs=%s",
                subsystem, func.__name__, args, kwargs,
            )
            try:
                result = func(*args, **kwargs)
                logger.info("[%s] %s returned: %s", subsystem, func.__name__, result)
                return result
            except Exception as e:
                logger.error("[%s] %s raised: %s", subsystem, func.__name__, e)
                raise
        return wrapper
    return decorator


def timed(operation_name: str) -> Callable:
    """Decorator that logs execution time."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug("[TIMER] %s took %.4fs", operation_name, elapsed)
            return result
        return wrapper
    return decorator
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/utils/test_decorators.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/utils/decorators.py nexus_strategy/tests/utils/test_decorators.py
git commit -m "feat: add log_decision and timed decorators"
```

---

## Chunk 4: Config Adapter and DI Container

### Task 11: Config Schema (Pydantic Validation)

**Files:**
- Create: `nexus_strategy/adapters/config/config_schema.py`
- Test: `nexus_strategy/tests/adapters/test_config/test_config_schema.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/adapters/test_config/test_config_schema.py`:
```python
"""Tests for Pydantic config validation schema."""
import pytest
from pydantic import ValidationError

from nexus_strategy.adapters.config.config_schema import (
    NexusConfig,
    GeneralConfig,
    RiskConfig,
    RegimeConfig,
    StrategyWeightsConfig,
    DCAConfig,
    ExitConfig,
    SentinelConfig,
    LearningConfig,
    AnalyticsConfig,
)


class TestGeneralConfig:
    def test_defaults(self):
        cfg = GeneralConfig()
        assert cfg.max_open_trades == 10
        assert cfg.base_timeframe == "5m"
        assert cfg.profile == "balanced"

    def test_custom_values(self):
        cfg = GeneralConfig(max_open_trades=5, profile="conservative")
        assert cfg.max_open_trades == 5

    def test_validation_max_open_trades_min(self):
        with pytest.raises(ValidationError):
            GeneralConfig(max_open_trades=0)


class TestRiskConfig:
    def test_defaults(self):
        cfg = RiskConfig()
        assert cfg.max_exposure == 0.85
        assert cfg.max_single_pair == 0.20
        assert cfg.kelly_fraction == 0.50

    def test_kelly_fraction_clamped(self):
        with pytest.raises(ValidationError):
            RiskConfig(kelly_fraction=1.5)


class TestNexusConfig:
    def test_full_default_config(self):
        cfg = NexusConfig()
        assert cfg.general.max_open_trades == 10
        assert cfg.risk.max_exposure == 0.85
        assert cfg.sentinel.enabled is True

    def test_from_dict(self):
        data = {
            "general": {"max_open_trades": 6, "profile": "conservative"},
            "risk": {"kelly_fraction": 0.30},
        }
        cfg = NexusConfig(**data)
        assert cfg.general.max_open_trades == 6
        assert cfg.risk.kelly_fraction == 0.30
        assert cfg.risk.max_exposure == 0.85  # default preserved

    def test_invalid_nested_raises(self):
        with pytest.raises(ValidationError):
            NexusConfig(general={"max_open_trades": -1})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/adapters/test_config/test_config_schema.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement config schema**

`nexus_strategy/adapters/config/config_schema.py`:
```python
"""Pydantic configuration validation schemas.

Part of the ADAPTERS layer - depends on pydantic (external).
Validates configuration loaded from TOML files.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GeneralConfig(BaseModel):
    max_open_trades: int = Field(default=10, ge=1, le=30)
    base_timeframe: str = Field(default="5m")
    informative_timeframes: list[str] = Field(default=["15m", "1h", "4h", "1d"])
    profile: str = Field(default="balanced")
    min_confidence: int = Field(default=45, ge=0, le=100)
    min_consensus: int = Field(default=2, ge=1, le=7)
    dry_run: bool = Field(default=True)


class RiskConfig(BaseModel):
    max_exposure: float = Field(default=0.85, ge=0.0, le=1.0)
    max_single_pair: float = Field(default=0.20, ge=0.01, le=0.50)
    max_sector: float = Field(default=0.35, ge=0.05, le=0.60)
    min_sectors: int = Field(default=3, ge=1)
    max_correlation: float = Field(default=0.85, ge=0.0, le=1.0)
    kelly_fraction: float = Field(default=0.50, ge=0.05, le=1.0)
    drawdown_caution: float = Field(default=0.05, ge=0.01, le=0.20)
    drawdown_warning: float = Field(default=0.10, ge=0.03, le=0.30)
    drawdown_critical: float = Field(default=0.15, ge=0.05, le=0.40)
    drawdown_catastrophic: float = Field(default=0.20, ge=0.10, le=0.50)


class RegimeConfig(BaseModel):
    transition_min_candles: int = Field(default=3, ge=1, le=20)
    panic_instant_transition: bool = Field(default=True)
    high_confidence_threshold: int = Field(default=70, ge=50, le=95)
    markov_lookback_candles: int = Field(default=2016, ge=288, le=8640)


class StrategyWeightsConfig(BaseModel):
    mean_reversion: float = Field(default=1.0, ge=0.0, le=3.0)
    trend_following: float = Field(default=1.0, ge=0.0, le=3.0)
    momentum_breakout: float = Field(default=1.0, ge=0.0, le=3.0)
    volatility_squeeze: float = Field(default=1.0, ge=0.0, le=3.0)
    volume_profile: float = Field(default=1.0, ge=0.0, le=3.0)
    divergence: float = Field(default=1.0, ge=0.0, le=3.0)
    market_structure: float = Field(default=1.0, ge=0.0, le=3.0)


class DCAConfig(BaseModel):
    enabled: bool = Field(default=True)
    max_dca_count: int = Field(default=4, ge=0, le=10)
    min_dca_interval_candles: int = Field(default=6, ge=1, le=48)
    require_technical_confirmation: bool = Field(default=True)


class ExitConfig(BaseModel):
    emergency_drop_pct: float = Field(default=0.10, ge=0.03, le=0.25)
    doom_stop_default: float = Field(default=0.08, ge=0.03, le=0.20)
    portfolio_total_loss_limit: float = Field(default=0.20, ge=0.10, le=0.40)
    trailing_atr_multiplier: float = Field(default=2.5, ge=1.0, le=5.0)
    time_decay_enabled: bool = Field(default=True)
    time_decay_rate_per_6h: float = Field(default=0.10, ge=0.0, le=0.25)
    max_time_decay: float = Field(default=0.50, ge=0.10, le=0.80)


class SentinelConfig(BaseModel):
    enabled: bool = Field(default=True)
    redis_url: str = Field(default="redis://localhost:6379/0")
    fallback_json_path: str = Field(default="sentinel_data.json")
    stale_threshold_seconds: int = Field(default=300, ge=30, le=600)
    risk_shutdown_threshold: int = Field(default=90, ge=50, le=100)
    risk_defensive_threshold: int = Field(default=80, ge=40, le=95)


class LearningConfig(BaseModel):
    enabled: bool = Field(default=True)
    min_trades_for_learning: int = Field(default=20, ge=5, le=100)
    base_learning_rate: float = Field(default=0.01, ge=0.001, le=0.10)
    max_parameter_drift: float = Field(default=0.50, ge=0.10, le=1.0)
    cooldown_candles: int = Field(default=288, ge=12, le=2016)
    backtest_learning: bool = Field(default=False)


class AnalyticsConfig(BaseModel):
    decision_logging: bool = Field(default=True)
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)
    trade_journal_enabled: bool = Field(default=True)
    daily_report: bool = Field(default=True)
    weekly_report: bool = Field(default=True)


class NexusConfig(BaseModel):
    """Root configuration model with all subsections."""
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    strategy_weights: StrategyWeightsConfig = Field(default_factory=StrategyWeightsConfig)
    dca: DCAConfig = Field(default_factory=DCAConfig)
    exit: ExitConfig = Field(default_factory=ExitConfig)
    sentinel: SentinelConfig = Field(default_factory=SentinelConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/adapters/test_config/test_config_schema.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/adapters/config/config_schema.py nexus_strategy/tests/adapters/test_config/test_config_schema.py
git commit -m "feat: add Pydantic config validation schema"
```

---

### Task 12: TOML Config Adapter (implements IConfigProvider)

**Files:**
- Create: `nexus_strategy/adapters/config/toml_adapter.py`
- Create: `nexus_strategy/config/base.toml`
- Create: `nexus_strategy/config/profiles/conservative.toml`
- Create: `nexus_strategy/config/profiles/balanced.toml`
- Create: `nexus_strategy/config/profiles/aggressive.toml`
- Create: `nexus_strategy/config/profiles/bear_market.toml`
- Test: `nexus_strategy/tests/adapters/test_config/test_toml_adapter.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/adapters/test_config/test_toml_adapter.py`:
```python
"""Tests for TOML config adapter."""
import pytest
import os
import tempfile
from pathlib import Path

from nexus_strategy.adapters.config.toml_adapter import TomlConfigAdapter
from nexus_strategy.adapters.config.config_schema import NexusConfig


class TestTomlConfigAdapter:
    @pytest.fixture
    def config_dir(self, tmp_path):
        """Create temp config dir with base.toml and profiles."""
        base_toml = tmp_path / "base.toml"
        base_toml.write_text("""
[general]
max_open_trades = 10
profile = "balanced"

[risk]
max_exposure = 0.85
kelly_fraction = 0.50

[sentinel]
enabled = true
""")
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        conservative = profiles_dir / "conservative.toml"
        conservative.write_text("""
[general]
max_open_trades = 6
min_confidence = 60
min_consensus = 3

[risk]
kelly_fraction = 0.30
""")

        aggressive = profiles_dir / "aggressive.toml"
        aggressive.write_text("""
[general]
max_open_trades = 15
min_confidence = 40
min_consensus = 2

[risk]
kelly_fraction = 0.65
""")

        return tmp_path

    def test_load_base_config(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        assert adapter.get("general.max_open_trades") == 10

    def test_load_with_profile(self, config_dir):
        adapter = TomlConfigAdapter(config_dir, profile="conservative")
        assert adapter.get("general.max_open_trades") == 6
        assert adapter.get("risk.kelly_fraction") == 0.30
        assert adapter.get("risk.max_exposure") == 0.85  # from base

    def test_get_profile(self, config_dir):
        adapter = TomlConfigAdapter(config_dir, profile="aggressive")
        assert adapter.get_profile() == "aggressive"

    def test_get_missing_key_returns_default(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        assert adapter.get("nonexistent.key", "fallback") == "fallback"

    def test_get_nested_key(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        assert adapter.get("sentinel.enabled") is True

    def test_runtime_override(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        adapter.override("general.max_open_trades", 5)
        assert adapter.get("general.max_open_trades") == 5

    def test_validated_config(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        cfg = adapter.get_validated_config()
        assert isinstance(cfg, NexusConfig)
        assert cfg.general.max_open_trades == 10

    def test_get_strategy_config(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        cfg = adapter.get_strategy_config("mean_reversion")
        assert isinstance(cfg, dict)

    def test_get_regime_weights(self, config_dir):
        adapter = TomlConfigAdapter(config_dir)
        weights = adapter.get_regime_weights("strong_bull")
        assert isinstance(weights, dict)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/adapters/test_config/test_toml_adapter.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement TOML config adapter**

`nexus_strategy/adapters/config/toml_adapter.py`:
```python
"""TOML configuration adapter - implements IConfigProvider.

Part of the ADAPTERS layer - depends on tomllib, pydantic, pathlib.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.adapters.config.config_schema import NexusConfig

logger = logging.getLogger("nexus.config")


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict. Override wins on conflicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class TomlConfigAdapter(IConfigProvider):
    """Loads configuration from TOML files with profile merging."""

    def __init__(
        self,
        config_dir: str | Path,
        profile: str | None = None,
    ):
        self._config_dir = Path(config_dir)
        self._profile = profile
        self._overrides: dict[str, Any] = {}
        self._data = self._load()
        self._callbacks: list[Any] = []

    def _load(self) -> dict[str, Any]:
        base_path = self._config_dir / "base.toml"
        if not base_path.exists():
            logger.warning("No base.toml found at %s, using defaults", base_path)
            return {}

        with open(base_path, "rb") as f:
            data = tomllib.load(f)

        if self._profile:
            profile_path = self._config_dir / "profiles" / f"{self._profile}.toml"
            if profile_path.exists():
                with open(profile_path, "rb") as f:
                    profile_data = tomllib.load(f)
                data = _deep_merge(data, profile_data)
                logger.info("Applied profile: %s", self._profile)
            else:
                logger.warning("Profile not found: %s", profile_path)

        return data

    def get(self, key: str, default: Any = None) -> Any:
        # Check overrides first
        if key in self._overrides:
            return self._overrides[key]

        # Navigate dot-separated key
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def get_profile(self) -> str:
        return self._profile or self.get("general.profile", "balanced")

    def get_strategy_config(self, strategy_name: str) -> dict[str, Any]:
        strategies = self._data.get("strategies", {})
        return dict(strategies.get(strategy_name, {}))

    def get_regime_weights(self, regime_name: str) -> dict[str, float]:
        weights = self._data.get("regime_weights", {})
        return dict(weights.get(regime_name, {}))

    def on_config_change(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def override(self, key: str, value: Any) -> None:
        """Set a runtime override (highest priority)."""
        self._overrides[key] = value
        logger.info("Runtime override: %s = %s", key, value)

    def get_validated_config(self) -> NexusConfig:
        """Get the full config validated through Pydantic."""
        merged = _deep_merge(self._data, {})
        # Apply overrides
        for key, value in self._overrides.items():
            parts = key.split(".")
            current = merged
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        return NexusConfig(**merged)

    def reload(self) -> None:
        """Reload configuration from disk."""
        old_data = self._data
        self._data = self._load()
        if self._data != old_data:
            for cb in self._callbacks:
                cb(self._data)
            logger.info("Configuration reloaded")
```

- [ ] **Step 4: Create base.toml**

`nexus_strategy/config/base.toml`:
```toml
# Nexus Strategy - Base Configuration

[general]
max_open_trades = 10
base_timeframe = "5m"
informative_timeframes = ["15m", "1h", "4h", "1d"]
profile = "balanced"
min_confidence = 45
min_consensus = 2
dry_run = true

[risk]
max_exposure = 0.85
max_single_pair = 0.20
max_sector = 0.35
min_sectors = 3
max_correlation = 0.85
kelly_fraction = 0.50
drawdown_caution = 0.05
drawdown_warning = 0.10
drawdown_critical = 0.15
drawdown_catastrophic = 0.20

[regime]
transition_min_candles = 3
panic_instant_transition = true
high_confidence_threshold = 70
markov_lookback_candles = 2016

[strategy_weights]
mean_reversion = 1.0
trend_following = 1.0
momentum_breakout = 1.0
volatility_squeeze = 1.0
volume_profile = 1.0
divergence = 1.0
market_structure = 1.0

[dca]
enabled = true
max_dca_count = 4
min_dca_interval_candles = 6
require_technical_confirmation = true

[exit]
emergency_drop_pct = 0.10
doom_stop_default = 0.08
portfolio_total_loss_limit = 0.20
trailing_atr_multiplier = 2.5
time_decay_enabled = true
time_decay_rate_per_6h = 0.10
max_time_decay = 0.50

[sentinel]
enabled = true
redis_url = "redis://localhost:6379/0"
fallback_json_path = "sentinel_data.json"
stale_threshold_seconds = 300
risk_shutdown_threshold = 90
risk_defensive_threshold = 80

[learning]
enabled = true
min_trades_for_learning = 20
base_learning_rate = 0.01
max_parameter_drift = 0.50
cooldown_candles = 288
backtest_learning = false

[analytics]
decision_logging = true
prometheus_enabled = true
prometheus_port = 9090
trade_journal_enabled = true
daily_report = true
weekly_report = true
```

- [ ] **Step 5: Create profile TOMLs**

`nexus_strategy/config/profiles/conservative.toml`:
```toml
[general]
max_open_trades = 6
min_confidence = 60
min_consensus = 3

[risk]
max_exposure = 0.65
kelly_fraction = 0.30

[dca]
max_dca_count = 2

[exit]
doom_stop_default = 0.06
```

`nexus_strategy/config/profiles/balanced.toml`:
```toml
# Balanced is the base config - no overrides needed
```

`nexus_strategy/config/profiles/aggressive.toml`:
```toml
[general]
max_open_trades = 15
min_confidence = 40
min_consensus = 2

[risk]
max_exposure = 0.90
kelly_fraction = 0.65
max_single_pair = 0.25

[dca]
max_dca_count = 6

[exit]
doom_stop_default = 0.12
```

`nexus_strategy/config/profiles/bear_market.toml`:
```toml
[general]
max_open_trades = 4
min_confidence = 70
min_consensus = 4

[risk]
max_exposure = 0.40
kelly_fraction = 0.25
max_single_pair = 0.15

[dca]
enabled = false

[exit]
doom_stop_default = 0.05
trailing_atr_multiplier = 2.0

[strategy_weights]
mean_reversion = 1.5
trend_following = 0.3
momentum_breakout = 0.2
volatility_squeeze = 0.5
volume_profile = 1.0
divergence = 1.5
market_structure = 0.5
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/adapters/test_config/test_toml_adapter.py -v
```
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add nexus_strategy/adapters/config/ nexus_strategy/config/
git commit -m "feat: add TOML config adapter with profiles and validation"
```

---

### Task 13: Dependency Injection Container

**Files:**
- Create: `nexus_strategy/application/dependency_container.py`
- Test: `nexus_strategy/tests/application/test_dependency_container.py`

- [ ] **Step 1: Write failing tests**

`nexus_strategy/tests/application/test_dependency_container.py`:
```python
"""Tests for DI container."""
import pytest
from unittest.mock import MagicMock

from nexus_strategy.application.dependency_container import DependencyContainer
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository
from nexus_strategy.domain.ports.data_port import IDataProvider


class TestDependencyContainer:
    def test_register_and_resolve(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock_config)
        resolved = container.resolve(IConfigProvider)
        assert resolved is mock_config

    def test_resolve_unregistered_raises(self):
        container = DependencyContainer()
        with pytest.raises(KeyError):
            container.resolve(IConfigProvider)

    def test_register_multiple_ports(self):
        container = DependencyContainer()
        mock_config = MagicMock(spec=IConfigProvider)
        mock_sentinel = MagicMock(spec=ISentinelProvider)
        mock_storage = MagicMock(spec=IStorageProvider)

        container.register(IConfigProvider, mock_config)
        container.register(ISentinelProvider, mock_sentinel)
        container.register(IStorageProvider, mock_storage)

        assert container.resolve(IConfigProvider) is mock_config
        assert container.resolve(ISentinelProvider) is mock_sentinel
        assert container.resolve(IStorageProvider) is mock_storage

    def test_register_overwrites(self):
        container = DependencyContainer()
        mock1 = MagicMock(spec=IConfigProvider)
        mock2 = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock1)
        container.register(IConfigProvider, mock2)
        assert container.resolve(IConfigProvider) is mock2

    def test_has(self):
        container = DependencyContainer()
        assert container.has(IConfigProvider) is False
        mock = MagicMock(spec=IConfigProvider)
        container.register(IConfigProvider, mock)
        assert container.has(IConfigProvider) is True

    def test_validate_all_ports_registered(self):
        container = DependencyContainer()
        # Should fail - nothing registered
        with pytest.raises(ValueError) as exc_info:
            container.validate()
        assert "missing" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest nexus_strategy/tests/application/test_dependency_container.py -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement DI container**

`nexus_strategy/application/dependency_container.py`:
```python
"""Dependency Injection container for Hexagonal Architecture.

Wires port interfaces to adapter implementations.
Part of the APPLICATION layer.
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

from nexus_strategy.domain.ports.data_port import IDataProvider, IIndicatorEngine
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.ports.storage_port import IStorageProvider
from nexus_strategy.domain.ports.analytics_port import IAnalyticsEmitter
from nexus_strategy.domain.ports.trade_repo_port import ITradeRepository

logger = logging.getLogger("nexus.di")

T = TypeVar("T")

# All required ports that must be registered before the system starts
REQUIRED_PORTS: list[type] = [
    IConfigProvider,
    IAnalyticsEmitter,
]

# Optional ports that have safe fallbacks
OPTIONAL_PORTS: list[type] = [
    IDataProvider,
    IIndicatorEngine,
    ISentinelProvider,
    IStorageProvider,
    ITradeRepository,
]


class DependencyContainer:
    """Simple DI container that maps port interfaces to adapter instances."""

    def __init__(self) -> None:
        self._registry: dict[type, Any] = {}

    def register(self, port_type: type, adapter_instance: Any) -> None:
        """Register an adapter instance for a port interface."""
        self._registry[port_type] = adapter_instance
        logger.info("Registered %s -> %s", port_type.__name__, type(adapter_instance).__name__)

    def resolve(self, port_type: type[T]) -> T:
        """Resolve a port to its registered adapter."""
        if port_type not in self._registry:
            raise KeyError(f"No adapter registered for port: {port_type.__name__}")
        return self._registry[port_type]

    def has(self, port_type: type) -> bool:
        """Check if a port has a registered adapter."""
        return port_type in self._registry

    def validate(self) -> None:
        """Validate that all required ports are registered."""
        missing = [p.__name__ for p in REQUIRED_PORTS if p not in self._registry]
        if missing:
            raise ValueError(f"Missing required port adapters: {', '.join(missing)}")
        logger.info("DI container validated: all required ports registered")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest nexus_strategy/tests/application/test_dependency_container.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add nexus_strategy/application/dependency_container.py nexus_strategy/tests/application/test_dependency_container.py
git commit -m "feat: add DI container for hexagonal port-adapter wiring"
```

---

### Task 14: Final - Run All Tests and Domain Models __init__

- [ ] **Step 1: Run all tests**

```bash
cd "/home/atabey/Belgeler/Snake oyunu/claude"
python -m pytest nexus_strategy/tests/ -v --tb=short
```
Expected: ALL PASS

- [ ] **Step 2: Verify hexagonal dependency rule**

```bash
# Domain files should NOT import from adapters or application
grep -r "from nexus_strategy.adapters" nexus_strategy/domain/ || echo "CLEAN: Domain has no adapter imports"
grep -r "from nexus_strategy.application" nexus_strategy/domain/ || echo "CLEAN: Domain has no application imports"
```
Expected: Both should print "CLEAN" messages

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Plan 1 - Hexagonal Foundation (models, ports, utils, config, DI)"
```
