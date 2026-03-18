# aShare User Manual

## 1) Overview

aShare is a **research-oriented A-share backtesting toolkit** built on Backtrader. It is designed for strategy prototyping and parameter studies, not for live trading execution. The current workflow centers on:

- single-symbol backtests (`ashare backtest`),
- YAML-based parameter sweep experiments (`ashare experiment`),
- rolling walk-forward validation (`ashare walk-forward`),
- data integration sanity checks (`ashare sanitytest`).

## 2) Environment and setup

### Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### Data provider selection

The default data provider is **BaoStock**. To switch provider:

```bash
export ASHARE_DATA_PROVIDER=tushare
export TUSHARE_TOKEN=<your_token>
```

You can also set cache directory:

```bash
export ASHARE_CACHE_DIR=./data_cache
```

### Run tests

```bash
pytest
```

## 3) CLI commands

### `ashare backtest`

Run one symbol with one strategy over one date range.

```bash
ashare backtest \
  --symbol 600519.SH \
  --strategy mean_reversion \
  --start 2024-01-01 \
  --end 2024-12-31
```

Current options:

- `--symbol` (required)
- `--strategy` (required)
- `--start` / `--end` (optional, strict `YYYY-MM-DD` when provided)
- `--plot` (CLI currently exposes it as a value option; if truthy it calls `cerebro.plot()`)

### `ashare experiment`

Two modes are supported.

#### A) YAML spec mode (recommended)

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

#### B) Direct CLI mode (no YAML file)

```bash
ashare experiment \
  --strategy mean_reversion \
  --symbols 600519.SH,000858.SZ \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --param z_entry=-1.2,-1.5 \
  --param z_exit=0.5,1.0
```

Supported overrides in both modes:

- `--start` / `--end`: overrides spec date range.
- `--param key=v`: sets a fixed parameter.
- `--param key=v1,v2`: sets a grid dimension.

### `ashare walk-forward`

Run rolling train/test optimization for one symbol.

```bash
ashare walk-forward \
  --symbol 600519.SH \
  --strategy mid_freq_ma \
  --start 2020-01-01 \
  --end 2021-12-31 \
  --train-window 180 \
  --test-window 60 \
  --param short_period=5,10 \
  --param long_period=20,30
```

### `ashare analyze`

Analyze a completed experiment output directory and generate a deterministic Markdown report.

```bash
ashare analyze outputs/mean_reversion_advanced_demo
```

Primary script entrypoint (recommended for automation):

```bash
python scripts/analyze_experiment.py outputs/mean_reversion_advanced_demo
```

### `ashare sanitytest`

Quick integration checks for data loading.

```bash
ashare sanitytest daily --symbol 000001.SZ
ashare sanitytest minute30 --symbol 000001.SZ
```

## 4) Strategy usage

Registered strategy names are currently:

- `mid_freq_ma`
- `core_satellite`
- `mean_reversion`
- `mean_reversion_advanced`

### `mean_reversion`

Key params:

- `trade_unit` (default `500`)
- `z_entry` (default `-1.5`)
- `z_exit` (default `1.0`)
- `allow_ladder` (present but not used by current logic)
- `ma_short` / `ma_trend` / `atr_period`

Behavior: enters when ATR-normalized z-score <= `z_entry`; exits full position when z-score >= `z_exit`.

### `mean_reversion_advanced`

Key params:

- `trade_unit` (default `500`)
- `z_entry` (default `-1.5`)
- `z_exit` (default `0.5`)
- `use_trend_filter` (default `true`)
- `use_atr_filter` (default `true`)

Behavior: same mean-reversion core entry/exit, plus optional trend and ATR filters, with per-bar diagnostics collection. Previously referred to as 'ART' due to a naming typo; this has now been corrected to ATR (Average True Range).

## 5) Experiment workflow

YAML experiment spec fields:

- `experiment_name` (required)
- `strategy` (required)
- `symbols` (required, non-empty list)
- `date_range.start` / `date_range.end` (required)
- `parameters` (optional fixed values)
- `grid_search` (optional lists for cartesian expansion)
- `execution` (optional runtime overrides: `initial_cash`, `commission`)

Parameter precedence in experiment execution:

1. Strategy defaults
2. YAML `parameters`
3. YAML `grid_search` expansion
4. CLI `--param` overrides (highest)

Date precedence:

- CLI `--start` / `--end` override YAML dates when provided.

## 6) Output files

### Experiment outputs (`outputs/<experiment_name>/`)

Per run (`run_001`, `run_002`, ...):

- `metrics.json`
- `config_snapshot.yaml`
- `run_result.json`
- `diagnostics.json` *(only when strategy emits diagnostics, e.g. `mean_reversion_advanced`)*
- `diagnostics_summary.json` *(same condition)*

Experiment-level:

- `summary.csv`
- `summary_sorted.csv`

`summary.csv`/`summary_sorted.csv` columns are fixed to:

`z_entry, z_exit, use_trend_filter, use_atr_filter, use_art_filter, total_return, sharpe, max_drawdown, num_trades`

### Walk-forward outputs (`experiments/walk_forward_<timestamp>/`)

- `results.csv`
- `summary.json`
- `windows.json`

## 7) Diagnostics

When a strategy has a `diagnostics` attribute (currently `mean_reversion_advanced`):

- `diagnostics.json` stores per-bar entries such as `zscore`, filter pass flags, signal/execution flags, and `blocked_by` reasons.
- `diagnostics_summary.json` stores aggregate counters:
  - `total_bars`
  - `entry_signals`
  - `executed_trades`
  - `blocked_by_trend`
  - `blocked_by_atr` *(legacy alias: `blocked_by_art`)*
  - `blocked_by_multiple`

For experiments, diagnostics are under each run folder in `outputs/<experiment_name>/run_xxx/`.

## 8) Runnable examples

```bash
# 1) Single backtest
ashare backtest --symbol 002850.SZ --strategy mean_reversion_advanced --start 2025-01-01 --end 2025-12-31

# 2) YAML experiment with CLI date override
ashare experiment configs/experiments/mean_reversion_advanced.yaml --start 2025-01-01 --end 2025-12-31

# 3) Direct CLI experiment mode
ashare experiment --strategy mean_reversion --symbols 002850.SZ --start 2025-01-01 --end 2025-12-31 --param z_entry=-1.2,-1.5 --param z_exit=0.5,1.0

# 4) Walk-forward
ashare walk-forward --symbol 600519.SH --strategy mid_freq_ma --start 2020-01-01 --end 2021-12-31 --train-window 180 --test-window 60 --param short_period=5,10 --param long_period=20,30
```

## 9) Known caveats

- `mean_reversion_advanced` filters can block most entries on some symbols/date ranges, resulting in very low trade counts.
- Sharpe can be `None` in short/flat runs; ranking fallback still works but interpretation needs caution.
- `summary.csv` keeps fixed columns focused on mean-reversion parameters, so non-mean-reversion parameter values are retained in per-run `run_result.json` rather than summary columns.
- Walk-forward outputs are written under `experiments/`, while experiment sweeps write under `outputs/`.


## Experiment Analysis

Use the research analysis layer after an experiment has already produced `summary.csv`, `summary_sorted.csv`, and per-run artifacts.

```bash
python scripts/analyze_experiment.py outputs/xxx
```

The generated `analysis_report.md` summarizes:

- total runs, best/average Sharpe, and best/average return,
- top-ranked parameter configurations from `summary_sorted.csv`,
- trade efficiency = `executed_trades / entry_signals`,
- filter impact rates such as ATR blocking and excursion blocking,
- grouped parameter contribution analysis for `use_multi_day_excursion`, `excursion_min`, and `excursion_window`.

Interpretation guidelines:

- **Trade efficiency** estimates how many candidate entry signals survive all enabled filters and actually execute. Very low values usually mean the strategy is over-filtered.
- **ATR block rate** shows how often the volatility gate rejects entries. ATR Ratio = ATR / Price. A high ATR rate suggests the ATR ratio threshold is too restrictive for the symbol or period.
- **Excursion block rate** shows how often the multi-day excursion gate suppresses trades. A high rate suggests the displacement requirement or lookback window may be too strict.

Suggested iteration workflow:

1. Start with the top-ranked configurations in the report.
2. If trade efficiency is low, relax `z_entry`, `z_exit`, or optional filters incrementally.
3. If ATR blocking dominates, lower the ATR ratio threshold or disable the filter for comparison runs.
4. If excursion blocking dominates, revisit `excursion_window` and `excursion_min`.
5. Re-run the same experiment spec so comparisons remain reproducible.
