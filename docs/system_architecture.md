# aShare System Architecture

## 1) System overview

aShare is currently a **research/backtesting platform** for A-share strategies. It provides a CLI-driven pipeline for:

- running single backtests,
- running multi-symbol parameter experiments,
- running walk-forward optimization,
- validating data integrations.

Scope is offline research (data load → backtest → artifacts), not production live trading.

## 2) High-level architecture

- **CLI layer** (`src/ashare/cli.py`)
  - command routing, argument validation, CLI overrides, orchestration.
- **Config/spec layer** (`src/ashare/config/*`, `src/ashare/experiment/spec.py`)
  - backtest defaults, YAML spec normalization, execution overrides.
- **Data layer** (`src/ashare/data/*`)
  - provider selection (`baostock`/`tushare`), cache-first loads, and Backtrader feed normalization remain local.
  - canonical bar contract + validation now delegate to `market-data-core` through a compatibility bridge (`ashare.data.core_bridge`).
- **Strategy layer** (`src/ashare/strategies/*`)
  - manual strategy registry + strategy implementations.
- **Engine layer** (`src/ashare/engine/*`)
  - Cerebro construction, analyzer registration, run execution, metrics extraction, diagnostics persistence.
- **Experiment/result layer** (`src/ashare/experiment/*`)
  - parameter expansion, experiment loop execution, run artifact writes, summary ranking.
- **Research utilities** (`src/ashare/research/*`)
  - walk-forward logic, experiment aggregation, diagnostics analysis, and Markdown report generation.

## 3) Execution flows

### A) Backtest flow

1. `ashare backtest` parses symbol/strategy/date args.
2. Strategy class resolved from registry.
3. `load_minute_30` loads data via provider + cache.
4. `run_backtest`:
   - builds Cerebro with broker settings,
   - adds data + strategy,
   - registers analyzers,
   - executes and extracts metrics.
5. CLI prints metrics; optional plotting when `--plot` is set.

### B) Experiment flow

1. `ashare experiment` loads YAML spec **or** builds spec from direct CLI args.
2. CLI merges YAML parameters/grid with `--param` overrides.
3. CLI applies date overrides (`--start`, `--end`) if provided.
4. `execute_experiment_spec` expands parameter sets (cartesian product).
5. For each symbol × parameter set:
   - run backtest,
   - write per-run artifacts (`metrics.json`, `config_snapshot.yaml`, `run_result.json`, optional diagnostics files).
6. `build_summary` generates `summary.csv` and `summary_sorted.csv`.

### C) Walk-forward flow

1. `ashare walk-forward` parses window and parameter grid args.
2. Generates rolling train/test windows.
3. Loads full date-range data once.
4. Per window:
   - optimize params in train segment,
   - apply best params on test segment,
   - store window result row.
5. Writes `experiments/walk_forward_<timestamp>/results.csv`, `summary.json`, `windows.json`.

## 4) Canonical experiment pipeline

The canonical experiment path is now `cli.experiment -> experiment.executor.execute_experiment_spec`.

There is also a legacy compatibility API in `ashare.research.experiment_runner.run_experiment()` that delegates to the same executor and writes a deprecation notice.

## 5) Parameter flow and precedence

Verified precedence for experiment runs:

1. **Strategy defaults** (Backtrader params)
2. **YAML `parameters`** (fixed params)
3. **YAML `grid_search`** (expanded parameter dimensions)
4. **CLI `--param`** overrides (highest)

Date precedence:

- CLI `--start`/`--end` > YAML `date_range.start`/`date_range.end`.

Execution overrides:

- YAML `execution.initial_cash` and `execution.commission` override `BacktestConfig` for experiment runs.
- `stamp_duty` and `slippage_perc` remain defaults unless changed elsewhere.

### Conditional Parameter Handling

- Some parameters depend on feature toggles and are normalized before execution.
- Example: `excursion_min` and `excursion_window` depend on `use_multi_day_excursion`.
- When `use_multi_day_excursion` is `False`, the runner normalizes those excursion parameters to `None` and deduplicates equivalent parameter combinations before running the experiment.

## 6) Strategy registry

Strategy registration is manual via `STRATEGY_REGISTRY` in `src/ashare/strategies/__init__.py`.

Current registry keys:

- `mid_freq_ma`
- `core_satellite`
- `mean_reversion`
- `mean_reversion_advanced`

Automatic strategy discovery is **not** implemented.

## 7) Output contract

### Experiment outputs (`outputs/<experiment_name>/`)

Per run folder (`run_###`):

- `metrics.json`
- `config_snapshot.yaml`
- `run_result.json`
- optional `diagnostics.json` + `diagnostics_summary.json` (if strategy emits diagnostics)

Experiment-level:

- `summary.csv`
- `summary_sorted.csv`

### Walk-forward outputs (`experiments/walk_forward_<timestamp>/`)

- `results.csv`
- `summary.json`
- `windows.json`

## 8) Diagnostics architecture

Diagnostics are strategy-driven:

- If strategy instance has `diagnostics`, `run_backtest` computes and stores `diagnostics_summary` counters.
- Diagnostics files are written when an output target exists (explicit `output_dir`, or derived from `experiment_name/run_id`).
- `mean_reversion_advanced` currently provides detailed per-bar diagnostics and trade reason tracking.

## 9) Current limitations / technical debt

- Artifact roots are split by workflow (`outputs/` for experiments vs `experiments/` for walk-forward).
- `summary.csv` uses a fixed mean-reversion-oriented column schema, which is lossy for unrelated strategy params.
- Backtest CLI has no direct `--param` injection for strategy params.
- `research.experiment_runner` remains as a deprecated wrapper API.
- `--plot` is declared as a value option in Click help (not a typical boolean flag UX).

## 10) Recommended next steps

1. Unify artifact root conventions across experiment and walk-forward outputs.
2. Make summary schema dynamic (or include run_id + params JSON column) to preserve all strategy params.
3. Add `ashare backtest --param key=value` for parity with experiment CLI.
4. Normalize `--plot` to a true boolean Click flag and keep docs/examples aligned.


## Signal Layer

### Multi-Day Excursion Component

The multi-day excursion component is a short-term excursion detector built from a rolling highest high and lowest low window. It complements z-score normalization and ATR-based volatility gating by identifying whether the market has actually displaced enough over the recent lookback window to justify an event-driven mean-reversion entry.

This component is intentionally modeled as a composable signal module instead of a hardcoded branch inside a single strategy. That keeps filter modularity and extensibility intact across the architecture, so YAML experiments, CLI overrides, and grid searches can enable or tune the filter without changing execution or data-loading layers.

The ATR filter uses Average True Range as a volatility measure and can be applied either as a gating filter or as a signal modifier for mean-reversion entries.

## Architecture Principles

- Favor composable signal modules so strategies can mix and match event detectors, normalizers, and gating filters without duplicating logic.
- Preserve filter modularity and extensibility so new optional constraints can be introduced through parameters, diagnostics, and experiment tooling rather than bespoke strategy forks.


### Research Layer

Responsibilities:
- experiment aggregation
- diagnostics analysis
- report generation

Design principles:
- deterministic (no LLM dependency)
- reproducible
- modular

The research layer consumes canonical experiment artifacts (`summary.csv`, `summary_sorted.csv`, `metrics.json`, `diagnostics_summary.json`) and turns them into reusable aggregate metrics and a structured Markdown report. This keeps post-experiment analysis separate from backtest execution while preserving CLI and script compatibility.


## 11) Phase 4 migration boundary

- Delegated to `market-data-core`: canonical bar schema contract resolution and validation entrypoints.
- Still local in `aShare`: provider APIs, cache implementation, backtest/strategy/research layers.
- Deferred: calendar/adjustment/storage policy harmonization after shared API stabilization.
