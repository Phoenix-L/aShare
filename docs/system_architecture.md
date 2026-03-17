# aShare System Architecture (Current Implementation)

## 1. High-level architecture (text diagram)

```text
User CLI
  ├─ ashare backtest
  ├─ ashare experiment
  └─ ashare walk-forward
        |
        v
Config resolution
  ├─ BacktestConfig defaults/env
  └─ Experiment YAML + CLI overrides
        |
        v
Data loading
  ├─ load_minute_30 / load_daily
  ├─ Provider factory (baostock|tushare)
  └─ cache read/write + schema validation
        |
        v
Execution engine
  ├─ run_backtest (Cerebro build/run)
  ├─ analyzers (returns/sharpe/drawdown/trades)
  └─ experiment loops (YAML CLI path or research runner)
        |
        v
Artifacts
  ├─ metrics.json
  ├─ config_snapshot.yaml
  ├─ summary.csv / summary_sorted.csv (YAML path)
  └─ results.csv + config.json (research runner path)
```

## 2. Data flow (YAML → runner → strategy → metrics)

1. `ashare experiment <spec.yaml>` parses and validates YAML spec.
2. CLI applies `--start/--end` and `--param` overrides.
3. CLI materializes parameter combinations (base params + grid cartesian product).
4. For each symbol, minute-30 data is loaded once for the selected date range.
5. For each parameter set, CLI calls `run_backtest(...)`.
6. Backtest engine builds broker/env, injects strategy params, executes analyzers.
7. Metrics are persisted per run and then aggregated to `summary.csv` + ranked summary.

## 3. Module responsibilities

- `src/ashare/cli.py`
  - Command parsing, validation, override application, orchestration, user-facing output.
- `src/ashare/config/*`
  - Backtest defaults, env loading, lightweight YAML scalar parsing utility.
- `src/ashare/data/*`
  - Provider selection, cache-first loading, schema enforcement, feed normalization.
- `src/ashare/strategies/*`
  - Strategy registry + strategy logic.
- `src/ashare/engine/*`
  - Cerebro construction, analyzer registration, execution and metrics extraction.
- `src/ashare/experiment/*`
  - Experiment spec normalization, parameter grid generation, result aggregation/ranking.
- `src/ashare/research/*`
  - Alternate experiment runner and walk-forward orchestration.

## 4. Parameter flow (critical)

### YAML experiment mode
Input sources:
1. YAML `parameters` (base)
2. YAML `grid_search` (dimensions)
3. CLI `--param` overrides

Merge semantics:
- `--param key=v` (single value) => force base parameter `parameters[key]=v`
- `--param key=v1,v2,...` (multi value) => force sweep dimension `grid[key]=[v1,v2,...]`

Final run params:
- `generate_parameter_sets({parameters, grid})` returns merged dict per run.
- Each run dict is passed to `run_backtest(..., strategy_params=params)`.

### Direct CLI experiment mode (`run_experiment`)
Input sources:
- `param_grid` from `--param`
- `base_params` optional (not exposed directly in this CLI path today)

Final run params:
- `final_params = {**base_params, **param_set}`
- each `final_params` goes into `run_backtest`.

## 5. Grid search flow

Two active implementations exist:
1. `experiment.grid.generate_parameter_sets` (YAML CLI path).
2. `engine.runner.expand_grid` (research runner / walk-forward path).

Both implement cartesian expansion of parameter lists.

## 6. CLI override hierarchy

### Date precedence
`CLI --start/--end` > YAML `date_range.start/end`.

### Parameter precedence (YAML mode)
`CLI --param` > YAML `parameters` / `grid_search` for same keys.

### Broker runtime (`execution` block)
In YAML mode only:
- `execution.initial_cash` and `execution.commission` override loaded defaults.
- other BacktestConfig fields (e.g., `stamp_duty`, `slippage_perc`) remain from global config unless changed elsewhere.

## 7. Known limitations

1. Two experiment pipelines with different artifact schemas (`outputs/` vs `experiments/`).
2. Grid search logic duplicated in two modules.
3. `backtest` command has no direct `--param` strategy injection.
4. Summary/ranking CSV only generated in YAML experiment path.
5. Data provider behavior differs by backend quality/coverage, especially minute-level history and turnover mapping.

## 8. Extensibility points already present

1. Provider abstraction (`DataProvider`) allows adding new market data sources.
2. Strategy registry supports incremental strategy additions.
3. `execution` section in experiment spec is a foothold for richer runtime controls.
4. `FUTURE_METRICS` placeholder in result module signals planned ranking/analysis extension.
5. `walk-forward` command pathway exists for phased research expansion.
