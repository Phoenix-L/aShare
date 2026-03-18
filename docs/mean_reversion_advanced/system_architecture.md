# System Architecture — mean_reversion_advanced

## 1. High-Level Architecture

The current workflow for `mean_reversion_advanced` is:

**CLI → Config → Data Loader → Strategy → Engine → Outputs → Research Layer**

At a high level:

1. the CLI parses a backtest or experiment request
2. YAML experiment specs are normalized into an execution spec
3. the data layer loads 30-minute OHLCV + turnover data into pandas
4. the engine converts the pandas frame into a Backtrader feed
5. the strategy computes z-score, ATR ratio, and optional filters bar by bar
6. the engine extracts metrics and diagnostics and writes run artifacts
7. the research layer aggregates experiment artifacts into quantitative summaries and a Markdown report

## 2. Module Breakdown

### Strategy Layer

Primary module:

- `src/ashare/strategies/mean_reversion_advanced.py`

Responsibilities:

- define strategy parameters
- resolve canonical ATR params and legacy aliases
- compute entry/exit logic
- track per-bar diagnostics and trade-level reason snapshots

### Indicators

Relevant code paths:

- `src/ashare/strategies/components/indicators.py`
- `src/ashare/indicators/multi_day_excursion.py`

Current indicator usage:

- `MA20` and `MA120` from `build_mean_reversion_indicators`
- `ATR14` from `build_mean_reversion_indicators` for z-score normalization
- `ATR3` from a dedicated `bt.indicators.ATR(..., period=3)` for the ATR ratio gate
- `atr_ratio = ATR3 / close` from `compute_atr_ratio`
- `MultiDayExcursion(...).excursion_ratio` for rolling displacement

### Engine

Relevant modules:

- `src/ashare/engine/runner.py`
- `src/ashare/engine/analyzers.py`

Responsibilities:

- build Backtrader `Cerebro`
- attach data feed and strategy
- register analyzers (Sharpe, drawdown, returns, trade analyzer)
- execute the backtest
- extract metrics
- aggregate and persist diagnostics when available

### Research Layer

Relevant modules:

- `src/ashare/research/analyzer.py`
- `src/ashare/research/report_generator.py`
- `scripts/analyze_experiment.py`

Responsibilities:

- ingest `summary.csv`, `summary_sorted.csv`, `metrics.json`, `diagnostics_summary.json`, `config_snapshot.yaml`
- compute aggregate metrics and grouped parameter analysis
- render `analysis_report.md`

## 3. Call Flow

### 3.1 Experiment execution

1. User runs:
   - `ashare experiment configs/experiments/mean_reversion_advanced.yaml`
2. `cli.py` validates optional `--start` / `--end` overrides and parses repeated `--param` values
3. `load_experiment_spec()` loads YAML and normalizes:
   - `experiment_name`
   - `strategy`
   - `symbols`
   - `date_range`
   - `parameters`
   - `grid_search`
4. CLI merges YAML params/grid with CLI overrides
5. `execute_experiment_spec()` expands the cartesian grid
6. `load_minute_30()` loads one pandas DataFrame per symbol
7. `run_backtest()` builds `Cerebro`, attaches the feed, attaches `MeanReversionAdvanced`, and executes
8. `extract_results()` reads analyzer outputs
9. `runner.py` aggregates diagnostics into `diagnostics_summary`
10. per-run artifacts are written to `outputs/<experiment_name>/run_xxx/`
11. `build_summary()` writes `summary.csv` and `summary_sorted.csv`

### 3.2 Post-experiment analysis

1. User runs:
   - `ashare analyze outputs/<experiment_name>`
   - or `python scripts/analyze_experiment.py outputs/<experiment_name>`
2. `analyze_experiment()` loads run artifacts and summary CSVs
3. grouped and aggregate metrics are computed
4. `generate_markdown_report()` renders a structured Markdown report
5. `analysis_report.md` is written into the same output directory

## 4. Parameter Flow

Current parameter flow for experiments is:

1. **Strategy defaults** from `MeanReversionAdvanced.params`
2. **YAML `parameters`** from `configs/experiments/*.yaml`
3. **YAML `grid_search`** expansion
4. **CLI `--param` overrides** (highest precedence)

Examples that match current CLI behavior:

```bash
ashare experiment \
  configs/experiments/mean_reversion_advanced.yaml \
  --param z_entry=-1.5,-2.0 \
  --param use_multi_day_excursion=true,false
```

Notes:

- `--param key=v` sets a fixed value
- `--param key=v1,v2` creates or overrides a grid dimension
- scalar coercion supports bool, int, float, then fallback string
- date precedence is separate: CLI `--start` / `--end` override YAML dates when provided

## 5. Data Flow

### Input

Current supported providers are selected through the provider factory:

- BaoStock (default)
- Tushare

The data loader expects and validates a pandas DataFrame with:

- `open`
- `high`
- `low`
- `close`
- `volume`
- `turnover_rate`
- `DatetimeIndex`

### Transformation

1. provider returns pandas data
2. loader validates schema and sorts index if needed
3. cache layer may serve or persist data
4. `to_backtrader_feed()` converts the normalized DataFrame into a Backtrader feed
5. if `turnover_rate` exists, `PandasDataWithTurnover` is used

## 6. Output Structure

Current experiment output layout:

```text
outputs/
  <experiment_name>/
    summary.csv
    summary_sorted.csv
    run_001/
      metrics.json
      diagnostics.json          # if diagnostics exist
      diagnostics_summary.json  # if diagnostics exist
      config_snapshot.yaml
      run_result.json
```

Current run-level artifacts relevant to `mean_reversion_advanced`:

- `metrics.json`: analyzer results such as return, Sharpe, drawdown, trade count
- `diagnostics_summary.json`: aggregated counters for trend / ATR / excursion blocking
- `config_snapshot.yaml`: the exact params used for that run
- `run_result.json`: normalized bundle of params, metrics, and metadata

## 7. Design Principles

The current implementation follows these principles:

- **modular**: strategy logic, indicators, engine, data, and research analysis are separated
- **reproducible**: experiments write deterministic artifacts that can be re-analyzed later
- **extensible**: new filters or parameters can be added without rewriting the full pipeline
- **no hardcoding of experiment results**: research reports are derived from saved artifacts, not manual interpretation

The system is also explicitly backward-compatible in some areas:

- canonical ATR params are preferred
- legacy alias field names are still accepted in strategy params and diagnostics summaries
- the research layer can read both canonical and legacy field names where needed
