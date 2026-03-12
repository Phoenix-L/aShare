# aShare System Architecture Design Report

## 1. System Overview

`aShare` is a Python-based personal A-share quantitative research and backtesting framework. Its current purpose is to help an individual trader quickly run strategy experiments via CLI, using market data providers (BaoStock/Tushare), Backtrader simulation, and modular strategy components.  

### Target Users
- Individual quantitative trader / independent researcher
- Developer-oriented user comfortable with CLI workflows

### Main Capabilities
- CLI-driven single-run backtesting (`ashare backtest ...`)
- Data provider abstraction and runtime switching (`baostock` default, `tushare` optional)
- Standardized OHLCV(+turnover) data schema
- Backtrader-based engine orchestration and analyzer extraction
- Strategy registry and strategy module separation
- A-share microstructure helper rules (e.g., 100-share lot sizing)
- Structured logging for observability

### Design Philosophy
- Keep the stack lightweight and composable
- Prioritize fast research iteration over operational complexity
- Encapsulate external APIs behind provider interfaces
- Make strategy logic independent from CLI plumbing

### Research Infrastructure vs Production Trading System
- **Research infrastructure** emphasizes hypothesis testing, reproducible backtests, feature iteration, and metrics extraction.
- **Production trading systems** additionally require robust broker integration, real-time risk controls, reconciliation, fault tolerance, and operational SLAs.

`aShare` currently sits clearly in the **research infrastructure** category.

---

## 2. High-Level Architecture

### Logical Layer Diagram

```text
CLI (Click)
  ↓
Configuration Layer
  ↓
Data Access Layer (Provider Factory -> BaoStock/Tushare)
  ↓
Data Normalization / Adapter Layer (Pandas -> Backtrader Feed)
  ↓
Backtest Engine (Cerebro Builder + Runner)
  ↓
Strategy Layer
  ↓
Constraints / Execution Rules
  ↓
Analyzers / Metrics
  ↓
Outputs (Console + Logs)
```

### Layer Responsibilities
- **CLI**: Accepts user inputs, resolves strategy, orchestrates run, prints summary metrics.
- **Configuration**: Holds cash/cost/slippage defaults and loading logic.
- **Data Access**: Abstract provider interface + concrete implementations (BaoStock/Tushare).
- **Normalization**: Guarantees strategy-facing feed compatibility.
- **Backtest Engine**: Sets broker model, attaches data/strategy/analyzers, executes run.
- **Strategy Layer**: Encodes trading signal logic and order behavior.
- **Constraints Layer**: Encapsulates A-share market rules.
- **Analyzers**: Produces return, drawdown, Sharpe, and trade statistics.
- **Outputs**: CLI metrics + structured log events for debugging/auditing.

---

## 3. Package Structure Analysis (`src/ashare`)

```text
src/ashare/
├── __main__.py
├── cli.py
├── config/
│   ├── loader.py
│   └── settings.py
├── constraints/
│   └── ashare.py
├── data/
│   ├── loaders.py
│   ├── normalizers.py
│   ├── tushare_client.py
│   └── providers/
│       ├── base.py
│       ├── baostock_provider.py
│       └── tushare_provider.py
├── engine/
│   ├── cerebro_builder.py
│   ├── analyzers.py
│   └── runner.py
├── strategies/
│   ├── base.py
│   ├── mid_freq_ma.py
│   └── __init__.py
├── sanitytests.py
└── utils/
    └── logging.py
```

### `cli`
- `click` command group with `backtest` and `sanitytest` commands.
- Primary orchestration point for end-to-end execution.

### `config`
- `BacktestConfig` dataclass for capital/cost/slippage model.
- Loader currently centered on defaults with optional argument override.

### `data`
- **Provider abstraction** via `DataProvider` interface.
- **Factory** chooses provider via `ASHARE_DATA_PROVIDER`.
- **Tushare provider** merges price and turnover from `daily_basic`.
- **BaoStock provider** handles login/session, symbol mapping, and turnover approximation/mapping.
- **Normalizer** converts pandas DataFrame to Backtrader feed with optional `turnover_rate` line.

### `strategies`
- Static strategy registry for CLI lookup.
- `BaseStrategy` centralizes transaction and trade lifecycle logging.
- `MidFreqMA` implements dual-MA crossover + turnover threshold.

### `engine`
- `cerebro_builder`: broker and slippage setup.
- `analyzers`: analyzer registration + metric extraction.
- `runner`: orchestration function for data feed, strategy execution, and outputs.

### `constraints`
- A-share lot sizing helpers (`LOT_SIZE=100`, round and buy-size calculation).

### `tests`
- Test files are scaffold placeholders right now; effective automated coverage is currently absent.

---

## 4. Data Flow (Backtest Execution Sequence)

### End-to-End Flow

```text
CLI command
  -> config load
  -> strategy class resolution
  -> data loader (provider selected)
  -> dataframe normalization
  -> backtrader feed creation
  -> cerebro initialization
  -> strategy execution
  -> analyzers
  -> metric extraction
  -> console/log output
```

### Concrete Runtime Sequence
1. User invokes `ashare backtest --symbol ... --strategy ... --start ... --end ...`.
2. CLI loads `BacktestConfig`.
3. CLI resolves strategy from registry.
4. CLI calls `load_minute_30(...)`.
5. Loader requests provider from provider factory.
6. Provider fetches and normalizes OHLCV+turnover data.
7. Runner builds cerebro and broker settings.
8. Runner converts DataFrame to Backtrader feed.
9. Runner attaches strategy + analyzers.
10. `cerebro.run()` executes simulation.
11. Analyzer metrics are extracted.
12. CLI prints final value/return/Sharpe/drawdown.

---

## 5. Dependency Graph

### Internal Module Dependencies (Simplified)

```text
cli
├── config.loader
├── data.loaders
├── strategies (registry)
├── engine.runner
├── sanitytests
└── utils.logging

engine.runner
├── config.settings
├── data.normalizers
├── engine.cerebro_builder
├── engine.analyzers
└── utils.logging

strategies.mid_freq_ma
├── strategies.base
└── constraints.ashare

data.loaders
└── data.providers (factory)
    ├── providers.baostock_provider
    └── providers.tushare_provider
```

### Coupling Assessment
- No obvious circular imports in current architecture.
- Tight coupling exists between engine and Backtrader types/APIs.
- CLI currently assumes 30-minute flow directly.
- Strategy registry is static and code-defined.

---

## 6. Strengths of Current Architecture

- Clean layered decomposition aligned with quant backtest workflow.
- Provider interface abstraction allows source switching without CLI rewrites.
- Standardized data schema reduces strategy/data mismatch.
- CLI is simple and productive for rapid experimentation.
- Structured logging improves run traceability.
- Constraints are explicit and reusable.

---

## 7. Architectural Weaknesses / Risks

- Test suite currently lacks executable test coverage.
- Single strategy in registry limits comparative experimentation.
- Backtrader dependency is deeply embedded in engine path.
- Cost model simplification (e.g., stamp duty handling) may reduce realism.
- No formal data cache layer; repeated API calls may be inefficient.
- No portfolio-level abstraction for multi-symbol research.
- Limited experiment management (no run metadata/result persistence standard).

---

## 8. Scalability Evaluation

### Capability Readiness
- **Multiple strategies**: partially supported (manual registry growth needed).
- **Portfolio-level backtests**: limited in current CLI/runner design.
- **Multi-symbol backtesting**: not first-class yet.
- **Walk-forward testing**: not built-in.
- **Hyperparameter optimization**: not built-in.
- **Live trading integration**: absent by design at current stage.

### Summary
Current architecture scales well for **single-user, single-strategy, single-symbol research loops**, but needs dedicated abstractions for portfolio simulation, experiment orchestration, and eventual live integration.

---

## 9. Recommended Architectural Improvements

Recommendations optimized for a **single individual quant investor**:

1. **Add experiment-runner module**
   - Batch run strategy params/symbols/windows and store comparable outputs.
2. **Introduce local market data cache**
   - Parquet-based cache keyed by provider/symbol/frequency/date range.
3. **Create portfolio research layer**
   - Multiple symbols, allocation policies, benchmark comparison.
4. **Improve strategy extensibility**
   - Plugin-like strategy discovery rather than static registry edits.
5. **Strengthen evaluation pipeline**
   - Persist equity curves, trade logs, analyzer snapshots, factor diagnostics.
6. **Expand testing pyramid**
   - Unit tests for constraints/normalizers + integration tests with mocked providers.
7. **Refine transaction cost model**
   - Side-specific fees/taxes and liquidity-aware slippage options.
8. **Add lightweight experiment tracking**
   - Run IDs, config snapshots, metrics table, reproducible outputs.

---

## 10. Future Evolution Roadmap

## Stage 1 — Research Framework (Current -> Near-Term)
Focus: stability and reproducibility.
- Implement meaningful automated tests.
- Add data cache and deterministic run artifacts.
- Expand strategy registry and parameter controls.

## Stage 2 — Strategy Laboratory
Focus: comparative research.
- Batch experiments and parameter sweeps.
- Walk-forward split support and report generation.
- Portfolio simulation for multi-symbol strategies.

## Stage 3 — Personal Trading Platform
Focus: controlled live deployment.
- Add paper/live adapters (broker abstraction).
- Risk checks and execution constraints before order placement.
- Daily reconciliation and operational observability dashboards.

---

## Additional Architecture Views

### Component Interaction Diagram

```text
[User]
  -> [CLI]
      -> [Config Loader]
      -> [Strategy Registry]
      -> [Data Loader]
          -> [Provider Factory]
              -> [BaoStock Provider | Tushare Provider]
      -> [Backtest Runner]
          -> [Cerebro Builder]
          -> [Feed Normalizer]
          -> [Analyzers]
      -> [Result Output + Structured Logging]
```

### Code Structure Summary
- Packaging uses `src/` layout and exposes `ashare` CLI script.
- Dependencies are minimal and practical for personal research tooling.
- Architecture is coherent and incremental-evolution friendly.
