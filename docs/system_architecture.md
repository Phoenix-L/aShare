# aShare System Architecture Design Report

## 1. Purpose and Positioning

`aShare` is a **personal quantitative research platform** for the Chinese A-share market.
Its primary purpose is to help an individual trader move efficiently through the loop:

`idea -> strategy implementation -> backtest -> metric review -> next experiment`

### What the System Is
- A single-user quant research laboratory.
- A CLI-first backtesting and experimentation workflow.
- A modular architecture for strategy iteration and measurement.

### What the System Is Not (Phase 1)
- Not a production live trading system.
- Not a broker-integrated execution platform.
- Not a distributed/cloud compute platform.

This aligns with the PRD scope: research infrastructure first, live trading later.

---

## 2. System Goals Aligned to PRD

The architecture is designed to satisfy the PRD goals:

- **G1 Rapid Strategy Development**: modular strategy framework + CLI execution.
- **G2 Reproducible Backtests**: deterministic config, standardized data flow, run outputs/logs.
- **G3 Strategy Comparison**: parameterized strategy design and upcoming experiment runner.
- **G4 Research Efficiency**: low-friction path from hypothesis to metrics.
- **G5 Architecture Longevity**: clear layering to support future portfolio and advanced research capabilities.

---

## 3. Architecture Layers (PRD-Aligned)

The architecture is organized around the PRD component model.

```text
CLI
  ↓
Configuration
  ↓
Data Layer
  ↓
Strategy Framework
  ↓
Backtest Engine
  ↓
Constraints Layer
  ↓
Analyzer / Metrics Layer
  ↓
Outputs
```

### 3.1 CLI
Responsibilities:
- parse backtest command inputs (`symbol`, `strategy`, date window, params)
- trigger a single deterministic run
- print concise summary metrics

### 3.2 Configuration
Responsibilities:
- hold capital, cost, slippage, and runtime settings
- support deterministic default config + explicit overrides
- snapshot run-time config for reproducibility

### 3.3 Data Layer
Responsibilities:
- provider abstraction (BaoStock, Tushare)
- symbol normalization and data schema unification
- API error handling and validation
- convert raw records to strategy-ready OHLCV(+turnover_rate)

### 3.4 Strategy Framework
Responsibilities:
- modular strategy files
- strategy registry and resolution
- parameterized strategy execution
- strategy-level signal, position sizing, and order logic

### 3.5 Backtest Engine
Responsibilities:
- build simulation environment
- attach data feeds, strategies, and analyzers
- apply broker/cost/slippage settings
- execute runs and return standardized results

### 3.6 Constraints Layer
Responsibilities:
- encode A-share market rules such as lot sizing
- extend to stamp duty, T+1, and price-limit constraints
- keep market microstructure logic isolated from strategy logic

### 3.7 Analyzer / Metrics Layer
Responsibilities:
- output required core metrics: total return, Sharpe, max drawdown, trade stats
- extend with win rate, profit factor, volatility, turnover ratio
- provide comparable result schema for experiment analysis

### 3.8 Outputs
Responsibilities:
- console summary for fast iteration
- persistent artifacts (`equity_curve.csv`, `trades.csv`, `metrics.json`, `plot.png`)
- run logs under `logs/run_YYYYMMDD.log`

---

## 4. Single-User Research Workflow

```text
Idea
  ↓
Implement or tune strategy
  ↓
Run CLI backtest
  ↓
Review metrics + artifacts
  ↓
Adjust parameters
  ↓
Run next experiment
```

Design implications:
- prioritize speed of iteration over operational complexity
- keep all modules scriptable and composable
- preserve run artifacts so decisions are evidence-based

---

## 5. Architecture Principles

1. **Research-first design**
   - optimize for hypothesis testing and iteration speed.

2. **Modular extensibility**
   - isolate CLI/config/data/strategy/engine/analyzers for safe evolution.

3. **Reproducibility by default**
   - deterministic inputs, standardized outputs, and run metadata logging.

4. **Data-provider abstraction**
   - shield strategy/engine from upstream API differences.

5. **Strategy isolation**
   - keep strategy logic independent from infrastructure concerns.

---

## 6. Current Gaps vs PRD Intent

1. **Data caching is missing**
   - repeated API pulls reduce iteration speed and reliability.

2. **Experiment management is weak**
   - no first-class batch runner for parameter sweeps and comparisons.

3. **Portfolio-level support is limited**
   - multi-symbol simulation and allocation workflows are not yet first-class.

4. **Analyzer depth is incomplete**
   - additional PRD-recommended metrics need to be promoted to default outputs.

5. **Parameter workflow needs hardening**
   - parameter schema/validation and sweep automation should be standardized.

6. **Test coverage remains thin**
   - architecture reliability and refactoring safety are constrained by limited tests.

---

## 7. Immediate Architecture Improvements

### 7.1 Data Caching Layer ✅ (Implemented in Phase 2)
- Implemented local Parquet cache to reduce repeated provider requests.
- Implemented deterministic keys: provider + symbol + frequency + date range.
- Integrated cache-first loading behavior for repeatable data retrieval.

### 7.2 Experiment Management
- Add structured experiment runs with run IDs, parameter sets, and result tables.
- Persist metadata for reproducible comparisons across hypotheses.

### 7.3 Multi-Symbol Portfolio Support
- Extend runner to accept symbol lists and allocation policies.
- Add portfolio-level result aggregation and metrics.

### 7.4 Analyzer Metric Expansion
- Promote win rate, profit factor, annualized volatility, turnover ratio to standard outputs.
- Keep core metrics stable for backward-compatible reporting.

### 7.5 Strategy Parameter Framework
- Standardize parameter declaration, validation, serialization, and sweep spaces.
- Ensure CLI can pass parameters in a repeatable machine-readable form.

### 7.6 Test Coverage Expansion
- Add unit tests for data normalization, constraints, analyzers, and strategy behavior.
- Add integration tests for end-to-end single-symbol backtest execution.

---

## 8. Imminent Engineering Actions

### Action 1 — Introduce Data Cache

Goal:
Reduce repeated API calls and improve research iteration speed.

Implementation:

`src/ashare/data/cache.py`

Features:
- parquet storage
- symbol-frequency-date indexing
- provider-aware cache keys
- freshness and integrity checks

---

### Action 2 — Experiment Runner

Goal:
Support structured strategy experimentation and comparison.

Create:

`src/ashare/research/experiment_runner.py`

Capabilities:
- batch strategy runs
- parameter sweeps
- result comparison
- run metadata persistence

---

### Action 3 — Portfolio Backtest Support

Goal:
Move from single-symbol research to portfolio-level analysis.

Enhance:

`src/ashare/engine/runner.py`

Support:
- multiple symbols
- capital allocation models
- portfolio metrics

---

### Action 4 — Analyzer Expansion

Goal:
Align default metrics with PRD recommended analytics depth.

Enhance:

`src/ashare/engine/analyzers.py`

Add metrics:
- win rate
- profit factor
- volatility
- turnover

---

### Action 5 — Test Infrastructure

Goal:
Improve reliability and refactoring safety.

Improve coverage in:
- `tests/test_engine.py`
- `tests/test_strategies.py`
- `tests/test_data_loaders.py`

Add:
- deterministic fixtures
- provider mocking strategy
- regression tests for metric extraction

---

## 9. Roadmap Alignment

### Phase 1 — Research Infrastructure (Current Focus)
- stable backtesting
- reliable data ingestion and validation
- reproducible outputs and efficient experimentation

### Phase 2 — AI-Assisted Research
- pattern discovery support
- parameter optimization workflows
- automated experiment diagnostics

### Phase 3 — Advanced Research Platform
- multi-symbol portfolio simulation
- experiment tracking and walk-forward validation
- research report generation

This sequence preserves the PRD direction: AI and advanced capabilities extend a solid core research infrastructure.

---

## 10. Consolidated Architecture View

```text
[User / Researcher]
  -> [CLI]
      -> [Configuration]
      -> [Data Layer]
          -> [Provider Abstraction: BaoStock | Tushare]
          -> [Normalization + (Planned) Cache]
      -> [Strategy Framework]
      -> [Backtest Engine]
          -> [Constraints Layer]
          -> [Analyzer / Metrics Layer]
      -> [Outputs: Console + Artifacts + Logs]
```

This architecture remains intentionally lightweight and modular for a single-user quant workflow while leaving clear extension points for upcoming engineering phases.

---

## 11. Architecture Implementation Roadmap

This roadmap turns the immediate architecture improvements into an ordered delivery plan with minimal disruption to current single-user research workflows.

### Why this order
- Build **test safety rails first** to reduce regression risk during structural changes.
- Improve **data reliability and repeatability** before scaling experiment volume.
- Add **experimentation and portfolio capabilities** only after foundations are stable.
- Expand **metrics and analytics depth** after run orchestration is mature.

### Phase 1 — Test Coverage Expansion
Phase 1 implements the foundational layers of the quant research testing pyramid: unit tests, data integrity tests, and minimal backtest integration tests. Strategy research validation tests are intentionally deferred to later phases to avoid premature complexity.

Scope (bottom layers of the quant research testing pyramid):
- Unit Tests
- Data Integrity Tests
- Backtest Integration Tests

Phase 1 modules:
- `tests/test_constraints.py`
- `tests/test_normalizers.py`
- `tests/test_data_loaders.py`
- `tests/test_data_integrity.py`
- `tests/test_mid_freq_ma.py`
- `tests/test_engine_runner.py`

Integration tests must include deterministic backtest validation.


### Phase 2 — Data Reliability Improvements

Phase 2 is now implemented with a local Parquet-backed data cache layer.

Improvements delivered:
- cache layer in `src/ashare/data/cache.py` for provider/symbol/frequency/date-range keyed storage
- deterministic data inputs via cache-first reads in data loaders
- improved backtest reproducibility by reusing identical cached datasets across runs

### Phase 2 — Data Cache Layer + Data Reliability

**Purpose**
- Reduce repeated API calls and improve deterministic data access for backtests/experiments.

**Architectural benefit**
- Decouples research speed from upstream provider latency/reliability.
- Creates a foundation for repeatable experiment runs.

**Modules affected**
- `src/ashare/data/cache.py` (new)
- `src/ashare/data/loaders.py`
- `src/ashare/data/providers/base.py`
- `src/ashare/config/settings.py` (cache toggles/paths)

**Estimated implementation complexity**
- **Medium-High** (cache key design, invalidation policy, integrity checks).

### Phase 3 — Strategy Parameter Framework + Experiment Runner

**Purpose**
- Enable structured strategy parameterization and repeatable batch experimentation.

**Architectural benefit**
- Converts ad-hoc single runs into reproducible experiment pipelines.
- Improves G3 (strategy comparison) and G4 (research efficiency).

**Modules affected**
- `src/ashare/research/experiment_runner.py` (new)
- `src/ashare/strategies/base.py`
- `src/ashare/strategies/__init__.py` (registry + parameter metadata)
- `src/ashare/cli.py` (parameter input and experiment commands)

**Estimated implementation complexity**
- **High** (schema design, CLI UX, result collation, metadata persistence).

### Phase 4 — Portfolio Backtest Support

**Purpose**
- Extend from single-symbol research to multi-symbol portfolio simulation.

**Architectural benefit**
- Adds realistic capital allocation research and broader strategy evaluation.
- Enables future roadmap items (batch testing, walk-forward workflows).

**Modules affected**
- `src/ashare/portfolio/portfolio_runner.py` (new, recommended)
- `src/ashare/engine/runner.py`
- `src/ashare/config/settings.py` (allocation model config)
- `src/ashare/cli.py` (multi-symbol inputs)

**Estimated implementation complexity**
- **High** (allocation logic, portfolio metric aggregation, interface updates).

### Phase 5 — Analyzer Expansion and Reporting Depth

**Purpose**
- Promote richer analysis outputs as first-class defaults.

**Architectural benefit**
- Improves transparency and decision quality with standardized advanced metrics.
- Makes experiment/portfolio comparisons more meaningful.

**Modules affected**
- `src/ashare/engine/analyzers.py`
- `src/ashare/engine/runner.py` (result packaging)
- `outputs/` contract documentation and serializers

**Estimated implementation complexity**
- **Medium** (metric definitions, edge-case handling, output schema compatibility).

### Recommended Delivery Milestones

1. **Milestone A (Phase 1 complete):** deterministic tests cover core single-symbol path.
2. **Milestone B (Phase 2 complete):** cache-enabled runs with validated data integrity.
3. **Milestone C (Phase 3 complete):** parameter sweeps and reproducible experiment reports.
4. **Milestone D (Phase 4 complete):** portfolio backtests available from CLI.
5. **Milestone E (Phase 5 complete):** expanded metrics integrated into default outputs.

This phased order minimizes implementation risk while steadily increasing research capability in line with the architecture principles and PRD-aligned goals.
