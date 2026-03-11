# NEXUS Trading Strategy - Design Document
## Multi-Strategy Ensemble with Self-Learning & Sentinel Engine

**Date:** 2026-03-11
**Status:** Approved
**Author:** Claude Opus 4.6 + User collaboration
**Framework:** Freqtrade IStrategy (INTERFACE_VERSION = 3)
**Market:** Spot only (Long)
**Base Timeframe:** 5m

---

## 1. EXECUTIVE SUMMARY

Nexus is a next-generation algorithmic trading strategy that surpasses NostalgiaForInfinityX7 in every dimension. It is a Multi-Strategy Ensemble system with a centralized orchestrator (Nexus Core), an external real-time data engine (Sentinel), self-learning capabilities, and portfolio-level risk management.

### Core Architecture: "Nexus" - Hexagonal (Ports & Adapters) with Centralized Brain

**Hexagonal Architecture** ensures zero spaghetti code. The domain layer (business logic) has ZERO dependencies on external systems. All external interactions happen through **Ports** (abstract interfaces) and **Adapters** (concrete implementations).

```
                    ┌─────────────────────────────────────┐
                    │         ADAPTERS (Outer Ring)         │
                    │                                       │
                    │  ┌─ FreqtradeAdapter (IStrategy)      │
                    │  ├─ RedisSentinelAdapter              │
                    │  ├─ TomlConfigAdapter                  │
                    │  ├─ SqliteStorageAdapter               │
                    │  └─ PrometheusAnalyticsAdapter         │
                    │                                       │
                    │    ┌─────────────────────────────┐    │
                    │    │    APPLICATION (Middle Ring)  │    │
                    │    │                               │    │
                    │    │  NexusCore (orchestrator)     │    │
                    │    │  Heartbeat (5m cycle)         │    │
                    │    │  DependencyContainer (DI)     │    │
                    │    │                               │    │
                    │    │    ┌─────────────────────┐    │    │
                    │    │    │  DOMAIN (Inner Core) │    │    │
                    │    │    │                       │    │    │
                    │    │    │  Models (immutable)   │    │    │
                    │    │    │  Ports (interfaces)   │    │    │
                    │    │    │  Services (logic)     │    │    │
                    │    │    │  Strategies (7+meta)  │    │    │
                    │    │    │                       │    │    │
                    │    │    │  ZERO external deps   │    │    │
                    │    │    └─────────────────────┘    │    │
                    │    │                               │    │
                    │    └─────────────────────────────┘    │
                    │                                       │
                    └─────────────────────────────────────┘

Sentinel Engine (external 24/7 service) ──[Redis/JSON]──> RedisSentinelAdapter
```

**Dependency Rule:** Domain → (nothing). Application → Domain + Ports. Adapters → Application + Domain + External libs.

**Port Interfaces (Domain defines, Adapters implement):**
- `IDataProvider` — market data, candles, indicators
- `ISentinelProvider` — real-time sentinel data
- `IConfigProvider` — configuration access
- `IStorageProvider` — persistence (trade journal, analytics)
- `IAnalyticsEmitter` — metrics and structured logging
- `ITradeRepository` — trade context persistence (Freqtrade custom_data)

### Key Differentiators vs NFIX7

| Feature | NFIX7 | NEXUS |
|---------|-------|-------|
| Architecture | Monolith spaghetti | Hexagonal (Ports & Adapters) |
| File Structure | Single 76K line file | 80+ modular files, 3 hexagonal rings |
| Strategy Count | 10 modes (label-based) | 7 independent sub-strategies + meta fusion |
| Regime Detection | NONE | 3-layer, 19 regimes, Markov transition model |
| Self-Learning | NONE | Indicator + strategy + regime + parameter learning |
| Validation | NONE | Every 5m all decisions re-validated |
| External Data | BTC price only | Sentinel: funding, on-chain, sentiment, orderbook |
| Risk Management | Per-trade | Portfolio: VaR, CVaR, correlation, sector |
| Position Sizing | Fixed multiplier | Kelly Criterion + 6 multipliers |
| Exit System | RSI-based layers | 5-layer engine + ATR trailing + time decay |
| DCA | 6 fixed levels | Regime-adaptive, technically conditional, self-learning |
| Configuration | Hardcoded | TOML profiles, hot-reload, validation, auto-adaptive |
| Logging | Minimal | Full decision logging, trade journal, anomaly detection |
| Extensibility | Very hard | New strategy = new file, implement BaseStrategy |
| Testability | Hard (coupled) | Domain tests pure, adapter tests isolated |
| Dependency Rule | Everything coupled | Domain has ZERO external imports |

---

## 2. PROJECT STRUCTURE (Hexagonal Architecture)

**Three Rings:** Domain (inner) → Application (middle) → Adapters (outer)

```
nexus_strategy/
│
├── nexus.py                              # Thin Freqtrade IStrategy entry point
│
├── domain/                               # ══ INNER CORE ══ (ZERO external deps)
│   ├── __init__.py
│   │
│   ├── models/                           # Immutable data models
│   │   ├── __init__.py                   # Re-exports all models
│   │   ├── regime.py                     # Regime enums + CompositeRegime
│   │   ├── signal.py                     # Signal, ExitSignal, SignalBundle
│   │   ├── risk.py                       # PortfolioState, PositionAction, DrawdownLevel
│   │   ├── trade_context.py              # TradeContext dataclass
│   │   └── market_state.py              # MarketState frozen snapshot
│   │
│   ├── ports/                            # Abstract interfaces (ABCs)
│   │   ├── __init__.py
│   │   ├── data_port.py                  # IDataProvider, IIndicatorEngine
│   │   ├── sentinel_port.py              # ISentinelProvider
│   │   ├── config_port.py                # IConfigProvider
│   │   ├── storage_port.py               # IStorageProvider
│   │   ├── analytics_port.py             # IAnalyticsEmitter
│   │   └── trade_repo_port.py            # ITradeRepository
│   │
│   ├── services/                         # Business logic (uses ONLY ports)
│   │   ├── __init__.py
│   │   ├── regime_service.py             # 3-layer regime detection
│   │   ├── signal_service.py             # Signal generation orchestration
│   │   ├── exit_service.py               # 5-layer exit engine
│   │   ├── position_service.py           # DCA, derisk, buyback, sizing
│   │   ├── risk_service.py               # VaR, CVaR, correlation, drawdown
│   │   └── learning_service.py           # Self-learning + validation
│   │
│   └── strategies/                       # Sub-strategy implementations
│       ├── __init__.py
│       ├── base_strategy.py              # Abstract base for all strategies
│       ├── mean_reversion.py
│       ├── trend_following.py
│       ├── momentum_breakout.py
│       ├── volatility_squeeze.py
│       ├── volume_profile.py
│       ├── divergence.py
│       ├── market_structure.py
│       └── meta_strategy.py              # Signal fusion engine
│
├── application/                          # ══ MIDDLE RING ══ (orchestration)
│   ├── __init__.py
│   ├── nexus_core.py                     # Central orchestrator
│   ├── heartbeat.py                      # 5m validation cycle (4 phases)
│   └── dependency_container.py           # DI container (wires ports→adapters)
│
├── adapters/                             # ══ OUTER RING ══ (external connections)
│   ├── __init__.py
│   │
│   ├── freqtrade/                        # Freqtrade adapter
│   │   ├── __init__.py
│   │   ├── strategy_adapter.py           # Maps IStrategy callbacks → domain
│   │   ├── data_adapter.py               # DataFrame → domain model conversion
│   │   └── trade_adapter.py              # Freqtrade Trade → domain mapping
│   │
│   ├── sentinel/                         # Sentinel communication adapter
│   │   ├── __init__.py
│   │   ├── redis_adapter.py              # Redis ISentinelProvider impl
│   │   └── json_adapter.py               # JSON file fallback impl
│   │
│   ├── config/                           # Configuration adapter
│   │   ├── __init__.py
│   │   ├── toml_adapter.py               # TOML loading + hot-reload
│   │   └── config_schema.py              # Pydantic validation schemas
│   │
│   ├── storage/                          # Persistence adapter
│   │   ├── __init__.py
│   │   ├── sqlite_adapter.py             # SQLite IStorageProvider impl
│   │   └── jsonl_adapter.py              # JSON Lines logging
│   │
│   └── analytics/                        # Analytics adapter
│       ├── __init__.py
│       ├── prometheus_adapter.py          # Prometheus IAnalyticsEmitter impl
│       └── structlog_adapter.py           # Structured logging
│
├── sentinel_engine/                      # ══ EXTERNAL SERVICE ══ (independent 24/7)
│   ├── __init__.py
│   ├── engine.py                         # Main async engine
│   ├── data_collectors/
│   │   ├── __init__.py
│   │   ├── websocket_collector.py
│   │   ├── funding_collector.py
│   │   ├── onchain_collector.py
│   │   ├── market_cap_collector.py
│   │   └── sentiment_collector.py
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── anomaly_analyzer.py
│   │   ├── correlation_analyzer.py
│   │   ├── sector_analyzer.py
│   │   ├── liquidity_analyzer.py
│   │   └── risk_scorer.py
│   ├── command_channel.py
│   └── sentinel_store.py
│
├── config/                               # Configuration files (not code)
│   ├── base.toml
│   ├── profiles/
│   │   ├── conservative.toml
│   │   ├── balanced.toml
│   │   ├── aggressive.toml
│   │   └── bear_market.toml
│   └── sub_strategies/
│       ├── mean_reversion.toml
│       ├── trend_following.toml
│       ├── momentum_breakout.toml
│       ├── volatility_squeeze.toml
│       ├── volume_profile.toml
│       ├── divergence.toml
│       └── market_structure.toml
│
├── utils/                                # Pure utility functions (no external deps)
│   ├── __init__.py
│   ├── math_utils.py                     # Hurst, rolling calcs, Kelly criterion
│   ├── cache.py                          # LRU + time-based cache
│   ├── decorators.py                     # @log_decision, @timed
│   └── constants.py                      # Coin lists, sector map, limits
│
└── tests/
    ├── __init__.py
    ├── domain/                           # Domain tests (fast, no mocks needed)
    │   ├── __init__.py
    │   ├── test_models/
    │   │   ├── __init__.py
    │   │   ├── test_regime.py
    │   │   ├── test_signal.py
    │   │   ├── test_risk.py
    │   │   ├── test_trade_context.py
    │   │   └── test_market_state.py
    │   ├── test_services/
    │   │   ├── __init__.py
    │   │   ├── test_regime_service.py
    │   │   ├── test_signal_service.py
    │   │   ├── test_exit_service.py
    │   │   ├── test_position_service.py
    │   │   ├── test_risk_service.py
    │   │   └── test_learning_service.py
    │   └── test_strategies/
    │       ├── __init__.py
    │       ├── test_mean_reversion.py
    │       ├── test_trend_following.py
    │       └── test_meta_strategy.py
    ├── adapters/                          # Adapter tests (mock externals)
    │   ├── __init__.py
    │   ├── test_freqtrade/
    │   ├── test_sentinel/
    │   ├── test_config/
    │   └── test_storage/
    ├── application/                       # Integration tests
    │   ├── __init__.py
    │   └── test_nexus_core.py
    └── utils/
        ├── __init__.py
        ├── test_math_utils.py
        ├── test_cache.py
        └── test_decorators.py
```

### Hexagonal Architecture Rules

1. **Domain imports NOTHING from adapters or application** — only stdlib, dataclasses, abc, typing, and pure math (numpy)
2. **Ports (ABCs) live in domain** — they define contracts, adapters implement them
3. **Application orchestrates** — uses domain services via dependency injection
4. **Adapters are swappable** — Redis can be swapped for JSON, SQLite for Postgres, Freqtrade for another framework
5. **Tests mirror the ring structure** — domain tests are pure (no mocks), adapter tests mock externals
6. **nexus.py is a thin shell** — it delegates everything to `application/nexus_core.py` through the DI container

---

## 3. DATA FLOW

```
Sentinel Engine (24/7) --> SentinelStore (Redis/JSON)
                                    |
                               (instant read)
                                    |
DataLayer:                          |
  SentinelBridge <------------------+
       |
       v
  MarketContext --> macro state, BTC analysis, inter-market
       |
       v
  IndicatorEngine --> adaptive indicator calculation
       |             --> composite indicators
       |             --> performance tracking (IndicatorRegistry)
       v
  RegimeDetector --> 3-layer regime detection
       |          --> Layer 1: Fast (5m-15m)
       |          --> Layer 2: Mid (1h-4h)
       |          --> Layer 3: Macro (1d + Sentinel)
       v
  === MarketState (frozen snapshot) ===
       |
SignalLayer:
       |
       +-> MeanReversion.generate()     -> Signal(confidence=78)
       +-> TrendFollowing.generate()    -> Signal(confidence=0)
       +-> MomentumBreakout.generate()  -> Signal(confidence=65)
       +-> VolatilitySqueeze.generate() -> Signal(confidence=0)
       +-> VolumeProfile.generate()     -> Signal(confidence=42)
       +-> Divergence.generate()        -> Signal(confidence=71)
       +-> MarketStructure.generate()   -> Signal(confidence=55)
       |
       v
  MetaStrategy.fuse() --> SignalBundle (final decision)
       |
ExecutionLayer:
       |
  RiskManager.validate() --> portfolio risk check
       |
  PositionSizer.calculate() --> Kelly + multipliers
       |
  TradeExecutor --> Freqtrade order
       |
  PositionManager.monitor() --> DCA, derisk, buyback
       |
  ExitEngine.evaluate() --> 5-layer exit
       |
IntelligenceLayer:
       |
  AnalyticsEngine <-- every decision logged
  PerformanceTracker --> strategy/indicator/regime performance
  SelfLearner --> weight updates (Bayesian)
  DecisionValidator --> every 5m re-validation
  CoherenceChecker --> system-wide consistency
  ParameterOptimizer --> auto-adaptive parameters
       |
  === Feedback Loop ===
  Intelligence -> DataLayer (indicator weights)
  Intelligence -> SignalLayer (strategy weights)
  Intelligence -> ExecutionLayer (risk parameters)
```

**Critical Design Decisions:**
1. MarketState is immutable (frozen snapshot) - data consistency guarantee
2. Signal confidence score (0-100) - not just buy/don't buy
3. Unidirectional data flow: Data -> Signal -> Execution -> Intelligence
4. Feedback only through parameters, never direct data manipulation
5. Sentinel has independent lifecycle - runs even if Freqtrade stops

---

## 4. REGIME DETECTION ENGINE

### 3-Layer Architecture

**Layer 1: FAST REGIME (5m-15m) - Market pulse**
- Volatility: ATR(14) normalized, BB Width(20,2.0), Parkinson, close-to-close
- Momentum: RSI(14) zone + slope, ROC(9) + acceleration, MFI(14)
- Trend: EMA(9/21/50) alignment, ADX(14), DI+/DI-, Supertrend, linear regression
- Volume: Volume/SMA(20), OBV slope, CMF(20)
- Output: 8 micro regimes (TRENDING_UP/DOWN, RANGING, VOLATILE, SQUEEZE, BREAKOUT_UP/DOWN, CHOPPY)

**Layer 2: MID REGIME (1h-4h) - Daily structure**
- Trend: EMA(12/26/50/200) alignment, EMA(200) slope, ADX, AROON, Ichimoku, MACD
- Statistical: Hurst Exponent, Rolling Sharpe, Skewness, Kurtosis, Z-score
- Structure: Pivot Points, Swing High/Low, HH/HL counter, S/R clusters
- Correlation: BTC correlation, BTC beta, sector average
- Output: 10 mid regimes (TREND_BULL/BEAR_STRONG/WEAK, RANGING_TIGHT/WIDE, ACCUMULATION, DISTRIBUTION, REVERSAL_BULLISH/BEARISH)

**Layer 3: MACRO REGIME (1d + Sentinel) - Big picture**
- Market Cycle: BTC 200 EMA, Golden/Death Cross, Monthly RSI
- Market Breadth: coins above 200 EMA, Altcoin Season Index, BTC Dominance, Stablecoin mcap
- Liquidity/Risk: Open Interest, Funding Rate, Liquidations, Exchange Flow, Risk Score
- Output: 9 macro regimes (BULL_EUPHORIA/HEALTHY/EARLY, BEAR_PANIC/GRIND/EARLY, TRANSITION_UP/DOWN, UNCERTAIN)

**Regime Synthesizer:**
- Combines 3 layers with compatibility matrix
- 3 layers aligned = HIGH confidence (90-100)
- 2 layers aligned = MEDIUM confidence (60-80)
- Layers conflicting = LOW confidence (30-50)
- Transition smoothing: min 3 candles, except PANIC (instant)
- Output: 19 synthesized regimes with confidence, duration, transition probability

### Regime -> Strategy Weight Matrix (example):

| Regime | MR | Trend | Momentum | Vol.Sq | Volume | Diverg | MktStr | Risk |
|--------|-----|-------|----------|--------|--------|--------|--------|------|
| STRONG_BULL | 0.5x | 2.0x | 1.8x | 1.0x | 1.2x | 0.8x | 1.5x | 1.2x |
| RANGING_TIGHT | 2.0x | 0.2x | 0.3x | 1.8x | 1.5x | 1.0x | 0.5x | 0.8x |
| PANIC | 0.3x | 0.0x | 0.0x | 0.0x | 0.0x | 0.5x | 0.3x | 0.3x |
| SQUEEZE | 0.5x | 0.3x | 1.5x | 2.5x | 1.0x | 0.8x | 1.0x | 0.7x |
| ACCUMULATION | 1.8x | 0.5x | 0.3x | 0.5x | 2.0x | 1.5x | 1.8x | 1.0x |

---

## 5. SELF-LEARNING & SYNCHRONIC VALIDATION

### Nexus Heartbeat (every 5m candle):

**Phase 1: Decision Validation (Introspection)**
- Regime validation: is previous regime decision still valid?
- Open position validation: are entry conditions still valid?
- Rejected signal validation: post-hoc analysis of rejections
- Missed opportunity analysis: what would have happened?

**Phase 2: Self-Learning Engine**
1. Indicator weight update: regime accuracy 40%, recent accuracy 30%, overall 20%, momentum 10%
2. Strategy weight update: Bayesian posterior with win rate, Sharpe, profit factor
3. Regime transition model: Markov chain rolling probabilities
4. Parameter micro-tuning: gradient-free optimization every 288 candles
5. Anomaly learning: pattern signatures for flash crash, pump trap, wick hunt

**Phase 3: Synchronic Update**
- Atomic update propagation in dependency order
- All updates applied simultaneously (all-or-nothing)

**Phase 4: Coherence Check**
- Contradiction detection across all subsystems
- System health metrics
- Automatic corrective actions (INFO -> WARNING -> ALARM -> CRITICAL -> FATAL)

### Safety Layers:
- Overfitting prevention: train/validation split, max parameter drift
- Catastrophic forgetting prevention: base values, max 50% deviation
- Feedback loop protection: learning rate limits, cooldown periods
- Live/backtest separation: self-learning OFF in backtest

---

## 6. SUB-STRATEGIES

### Common Interface (BaseStrategy):
```
generate_signal(market_state) -> Signal
validate_existing_position(trade, market_state) -> PositionAction
generate_exit_signal(trade, market_state) -> ExitSignal
get_optimal_regimes() -> list[Regime]
calculate_stop_loss(trade, market_state) -> float
calculate_take_profit(trade, market_state) -> list[TakeProfit]
get_required_indicators() -> list[IndicatorSpec]
```

### Strategy 1: Mean Reversion
- Philosophy: Price reverts to mean after extreme deviation
- Optimal regimes: RANGING_TIGHT, RANGING_WIDE, WEAK_BEAR, ACCUMULATION
- 5 entry layers: oversold detection, deviation measurement, reversal signal, multi-TF confirm, protection filters
- Exit: target mean (EMA50/VWAP), partial TP, ATR*2.5 stop, 48h time limit

### Strategy 2: Trend Following
- Philosophy: Ride the trend until it ends
- Optimal regimes: STRONG_BULL, MODERATE_BULL, BREAKOUT_BULL
- 4 entry types: EMA pullback, BB mid bounce, Supertrend flip, MACD resume
- Exit: trend termination signals, Chandelier Exit, ATR*3.0 trail, no time limit

### Strategy 3: Momentum Breakout
- Philosophy: Capture consolidation breakouts
- Optimal regimes: SQUEEZE, BREAKOUT_BULL, TRANSITION_UP, ACCUMULATION
- 4 breakout types: BB breakout, resistance break, Keltner+BB squeeze release, volume explosion
- Critical: fake breakout filter (candle body, next candle confirm, BTC check)
- Exit: failed breakout = immediate exit, ATR*2.0 trail, 24h time limit

### Strategy 4: Volatility Squeeze
- Philosophy: Catch the energy release from volatility compression
- Optimal regimes: SQUEEZE, RANGING_TIGHT, ACCUMULATION
- Squeeze detection: BB inside Keltner, duration > 6 candles, ATR declining
- Direction prediction: momentum + structural + multi-TF (score > 0.65 = UP)
- Exit: failed release = 6 candle exit, ATR*2.0 trail

### Strategy 5: Volume Profile / VWAP
- Philosophy: Follow institutional money
- Optimal regimes: MODERATE_BULL, ACCUMULATION, RANGING_WIDE
- 3 VWAP types: bounce, -2sigma reversal, reclaim
- 3 VP types: POC bounce, LVN breakout, Value Area reclaim
- Smart money detection: OBV divergence, CMF, large volume bars, volume delta
- Exit: VWAP+2sigma, POC break, smart money exit signals

### Strategy 6: Multi-Timeframe Divergence
- Philosophy: When price and indicators disagree, indicators are right
- Optimal regimes: REVERSAL_BULLISH, WEAK_BEAR
- 5 indicators: RSI, MACD, OBV, CCI, MFI divergence
- Multi-TF: same divergence on 2+ TFs = HIGH confidence, 3 TFs = VERY HIGH
- Exit: target reached, reverse divergence, failed reversal candle

### Strategy 7: Market Structure
- Philosophy: Read price structure - HH/HL/LH/LL and break points
- Optimal regimes: TRANSITION_UP, ACCUMULATION, BREAKOUT_BULL
- Swing point analysis: BOS (Break of Structure), CHoCH (Change of Character)
- Order Block analysis: bullish OB, Fair Value Gap, Liquidity Sweep
- Exit: structure broken (LL in uptrend), reverse CHoCH = immediate exit

### Meta-Strategy (Signal Fusion Engine):
1. Filter: confidence < 40 eliminated, inactive regime strategies removed
2. Weighted scoring: confidence * regime_weight * performance_weight * indicator_reliability
3. Correlation penalty: similar strategies penalized to ensure true diversity
4. Consensus: >=5/7 = STRONG (1.3x), >=3/7 = NORMAL (1.0x), 2/7 = WEAK (0.6x), 1/7 = SINGLE (0.3x if conf>85)
5. Final: composite >= 70 STRONG BUY, >= 55 BUY, >= 45 WEAK BUY, < 45 REJECT

---

## 7. EXIT ENGINE (5 Layers)

**Layer 1: Emergency Exit** - Survival (cannot be disabled, not affected by self-learning)
- Black Swan: 10%+ drop in 5m, 15%+ in 3 candles, 10x volume spike + drop
- Doom Stop: regime-adaptive thresholds (-4% PANIC to -15% STRONG_BULL)
- System Protection: portfolio total loss > -20% = CLOSE ALL

**Layer 2: Technical Exit** - Strategy-based
- Each sub-strategy provides its own exit signal with urgency (0-100)
- Strategy-independent technical exits: RSI>78, bearish divergence, EMA cross, CHoCH
- Urgency aggregation: 1 signal = watch, 2-3 = partial, 4+ = full exit

**Layer 3: Regime Exit** - Big picture changed
- Regime compatibility matrix: favorable/neutral/unfavorable transitions
- Regime-position mismatch score: < 30 = exit, 30-60 = reduce, > 60 = hold
- Sentinel override: risk 80+ = no new entries, 90+ = gradual full exit

**Layer 4: Portfolio Exit** - Risk management
- Drawdown exceeded: close worst performing positions
- Correlation exceeded: close worst correlated duplicate
- Sector concentration: reduce overweight sectors
- Slot exceeded: close lowest-scored position
- VaR exceeded: reduce highest VaR contributor
- Position scoring: PnL 25% + signal strength 20% + regime compat 20% + time penalty 15% + strategy conf 20%

**Layer 5: Profit Optimizer** - Maximum profit
- Partial Take Profit: 4-level (25% each, regime-adjusted)
- Adaptive Trailing: ATR-based (regime-adjusted multiplier), PSAR, Chandelier
- Trailing Ratchet: tighter as profit grows (ATR*3.0 at 0% to ATR*1.2 at 15%+)
- Time Decay: exit thresholds tighten with position age (10%/6h, max 50%)
- Re-entry Logic: if early exit was wrong, re-enter smaller (max 2 re-entries)

---

## 8. POSITION MANAGEMENT & RISK ENGINE

### DCA System (Regime-Adaptive):
- DCA allowed/forbidden per regime (PANIC/STRONG_BEAR/DISTRIBUTION = NO)
- Dynamic levels per regime (STRONG_BULL: 4 levels up to -16%, WEAK_BEAR: 2 levels up to -5%)
- Technical conditions required (support, oversold, reversal signals)
- Self-learning adjustment: success rate > 60% = loosen, < 40% = tighten
- Post-DCA exit: narrower TP targets (DCA1: +2.5%, DCA4+: +1.0%)

### Derisk System (4 Levels):
- Level 1 (-5%): sell 15% (skip if RSI < 30)
- Level 2 (-8%): sell 25%
- Level 3 (-12%): sell 40%
- Level 4 (-16%): sell 80%, remaining = "zombie position" (72h expiry)
- 24h re-entry ban on derisked pairs

### Buyback System:
- Conditions: previous trade profitable, price dropped, regime suitable, technical support
- Sizing: 60% of previous position (80% if confidence > 80%)
- Max 2 buybacks per pair per 24h

### Position Sizer (Kelly Criterion):
- Half-Kelly base size
- 6 multipliers: regime, confidence, consensus, drawdown, correlation, sentinel
- Limits: min 5%, max 15% per trade, max 85% total exposure, max 20% per pair

### Risk Manager (Portfolio Level):
- Drawdown management: 5 levels (NORMAL -> CAUTION -> WARNING -> CRITICAL -> CATASTROPHIC)
- Recovery mode: start at 25% size, increment 25% per 2% gain, full at 95% of peak
- Correlation management: rolling correlation matrix, max 0.85 between positions
- Sector distribution: max 35% per sector, min 3 sectors
- VaR/CVaR: Historical + Parametric + Conditional, portfolio-level limits
- Dynamic slot limits per regime (STRONG_BULL=12, PANIC=2)

---

## 9. SENTINEL ENGINE (External 24/7 Service)

### Architecture:
- Independent Python service (asyncio-based)
- Runs independently of Freqtrade, 24/7
- 5 data collectors running in parallel async tasks
- 5 analyzers triggered on new data arrival
- Command channel updated every 10 seconds

### Data Collectors:
1. **WebSocketCollector** (INSTANT): BTC/top50 tickers, orderbook, trades, liquidations
2. **FundingCollector** (30s): funding rate, open interest, long/short ratio, taker volume
3. **OnChainCollector** (60s): exchange flow, whale transactions, miner flow, stablecoin mint/burn
4. **MarketCapCollector** (60s): total mcap, BTC dominance, sector mcaps, altcoin season
5. **SentimentCollector** (5m): Fear & Greed, Google Trends

### Analyzers:
1. **AnomalyAnalyzer**: flash crash precursors, correlation breaks, spoofing
2. **CorrelationAnalyzer**: top 30 correlation matrix, sector correlation
3. **SectorAnalyzer**: sector momentum scores, rotation detection, cross-sector flows
4. **LiquidityAnalyzer**: orderbook depth, wall detection, spoofing detection
5. **RiskScorer**: composite risk score (0-100) from 8 weighted factors

### Command Channel Output:
- strategy_mode: NORMAL / CAUTIOUS / DEFENSIVE / SHUTDOWN
- max_new_entries, preferred_sectors, avoid_sectors
- position_size_modifier, dca_allowed
- Full market state: risk score, market phase, funding, on-chain, sentiment

### Storage:
- Primary: Redis (ultra-fast read/write)
- Fallback: JSON file
- Historical: SQLite
- Strategy reads via SentinelBridge every 5m + event-triggered for urgent alerts

---

## 10. INTELLIGENCE LAYER

### Analytics Engine:
- Every decision logged with full reasoning (entry, exit, DCA, derisk, rejection)
- Storage: JSON Lines (fast write) + SQLite (queryable) + Prometheus (metrics)

### Performance Tracker:
- Per strategy (regime-segmented): win rate, avg profit, profit factor, Sharpe, Sortino, max DD
- Per indicator: signal accuracy, false positive rate, contribution score, redundancy
- Per regime: total PnL, trade count, detection accuracy
- Portfolio: equity curve, Sharpe, Calmar, total metrics

### Trade Journal:
- Full trade story: entry -> DCA -> partial TP -> regime changes -> exit
- Post-analysis with grade (A+ to F)

### Anomaly Detector:
- Performance anomalies: consecutive losses, win rate drops, drawdown speed
- Signal anomalies: too many/few signals, single strategy dominance
- System anomalies: heartbeat delays, Sentinel connection, resources

### Report System:
- Daily summary (00:00 UTC)
- Weekly analysis (Monday)
- Monthly comprehensive report (1st of month)
- Format: JSON (machine) + Markdown (human)

---

## 11. CONFIGURATION SYSTEM

### TOML-based with Override Hierarchy:
1. base.toml (defaults)
2. profiles/balanced.toml (selected profile)
3. sub_strategies/mean_reversion.toml (strategy-specific)
4. Runtime (auto-adaptive changes)
5. Manual override (user live changes)

### Profiles:
- **Conservative**: 6 trades, min confidence 60, consensus 3/7, Kelly 0.30
- **Balanced**: 10 trades, min confidence 45, consensus 2/7, Kelly 0.50
- **Aggressive**: 15 trades, min confidence 40, consensus 2/7, Kelly 0.65
- **Bear Market**: 4 trades, min confidence 70, consensus 4/7, DCA disabled

### Validation:
- Type checking, min/max bounds, dependency checks, consistency checks
- Invalid config = strategy WILL NOT START (no silent corruption)

### Hot-Reload:
- File change detection via watchdog
- Apply changes without restart
- Parameter change history logged

---

## 12. TECHNOLOGY STACK

### Core:
- Python 3.11+, Freqtrade >= 2024.x
- pandas, numpy, ta-lib, pandas-ta, scipy

### Sentinel:
- asyncio, aiohttp, websockets, ccxt
- redis-py, orjson, aiosqlite

### Configuration:
- tomllib (Python 3.11 builtin), pydantic, watchdog

### Analytics:
- prometheus_client, structlog, sqlite3

### Testing:
- pytest, pytest-asyncio, pytest-mock, hypothesis

### Freqtrade Integration:
- nexus.py implements IStrategy (INTERFACE_VERSION = 3)
- All Freqtrade callbacks mapped to Nexus subsystems
- `--strategy Nexus --strategy-path nexus_strategy/`

---

## 13. DATA MODELS

### Core Models:
- **CompositeRegime**: micro + mid + macro + synthesized + confidence + metadata
- **Signal**: pair, strategy, action, confidence, stop/TP, reasoning
- **SignalBundle**: composite score, consensus, merged signals, regime, risk rating
- **MarketState**: frozen snapshot of all data (indicators, regime, sentinel, BTC, performance)
- **TradeContext**: full position context (entry signal, DCA/derisk history, PnL tracking)
- **PortfolioState**: equity, drawdown, positions, VaR, correlation, sector distribution

All MarketState objects are immutable (frozen dataclass) to ensure data consistency.

---

## 14. PRE-IMPLEMENTATION REQUIREMENT

**MANDATORY: Before writing ANY code, read ALL relevant Freqtrade official documentation page by page, line by line:**
- Strategy Interface (IStrategy)
- Strategy Callbacks
- Indicator Library
- Position Management (adjust_trade_position)
- Custom Exit (custom_exit)
- Custom Stake Amount
- Informative Pairs
- Data Handling
- Backtesting
- Configuration
- Bot Loop
- Order Management

This ensures full compatibility and zero assumptions.
