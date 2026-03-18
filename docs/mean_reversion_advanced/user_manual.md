# User Manual — mean_reversion_advanced

## 1. Quick Start

Run the shipped experiment spec:

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

This launches a parameter sweep for `mean_reversion_advanced`, writes run artifacts under `outputs/mean_reversion_advanced_demo/`, and creates experiment-level summary CSV files.

## 2. Key Parameters

### `z_entry`

Entry threshold for the ATR-normalized z-score.

- more negative values make entries rarer
- less negative values make the strategy react sooner

### `z_exit`

Exit threshold for the same z-score.

- lower values exit earlier
- higher values hold longer waiting for more mean reversion

### `use_atr_filter`

Enables the ATR ratio filter.

Current effective behavior:

- if omitted, ATR filtering is enabled by default
- legacy `use_art_filter` is still accepted, but deprecated

### `atr_ratio_min`

Minimum ATR ratio required for the ATR filter to pass.

Definition:

- `ATR Ratio = ATR / Price`

Current effective default:

- `0.02` if neither `atr_ratio_min` nor legacy `art_threshold` is provided

### `use_multi_day_excursion`

Turns the excursion filter on or off.

- `false`: ignore excursion gating
- `true`: require sufficient rolling displacement before entry

### `excursion_min`

Minimum excursion ratio required when the excursion filter is enabled.

- higher values are more restrictive
- lower values allow more candidate reversals through

### `excursion_window`

Lookback window used to compute the rolling high-low excursion ratio.

- smaller windows react faster
- larger windows smooth recent displacement and usually require more persistent range expansion

## 3. Running Experiments

### YAML-driven experiment

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

### YAML + CLI overrides

```bash
ashare experiment \
  configs/experiments/mean_reversion_advanced.yaml \
  --param z_entry=-1.5,-2.0 \
  --param use_multi_day_excursion=true,false
```

### Important override behavior

Current CLI behavior:

- repeated `--param` entries are supported
- `--param key=v` sets a fixed value
- `--param key=v1,v2` creates a grid dimension
- `--start` / `--end` override the YAML date range

Example with date override:

```bash
ashare experiment \
  configs/experiments/mean_reversion_advanced.yaml \
  --start 2025-08-01 \
  --end 2026-01-31
```

## 4. Understanding Output

After an experiment, look at three main layers of output.

### `summary.csv`

This is the unsorted experiment-wide summary table.

Current columns are written from the experiment result layer and include fields such as:

- `z_entry`
- `z_exit`
- `use_trend_filter`
- `use_atr_filter`
- `use_art_filter` *(legacy alias column retained for compatibility)*
- `use_multi_day_excursion`
- `excursion_window`
- `excursion_min`
- `atr_ratio_min`
- `total_return`
- `sharpe`
- `max_drawdown`
- `num_trades`

### `summary_sorted.csv`

This contains the same rows, sorted by:

1. Sharpe descending
2. total return descending

Use this file to inspect the top-ranked parameter combinations quickly.

### `run_xxx/`

Each run folder contains detailed artifacts:

- `metrics.json`
- `diagnostics.json` *(when diagnostics exist)*
- `diagnostics_summary.json`
- `config_snapshot.yaml`
- `run_result.json`

For `mean_reversion_advanced`, `diagnostics_summary.json` is especially useful for understanding why entries did or did not convert into trades.

## 5. Running Analysis

Generate a Markdown report from a completed experiment:

```bash
python scripts/analyze_experiment.py outputs/xxx
```

If the package entrypoint is installed, you can also use:

```bash
ashare analyze outputs/xxx
```

The generated `analysis_report.md` currently includes:

- summary metrics
- top configurations
- trade efficiency
- filter impact
- excursion parameter contribution analysis
- rule-based insights and recommendations

## 6. How to Tune Strategy

Practical tuning workflow for the current implementation:

1. start with `summary_sorted.csv` to see the best Sharpe / return rows
2. run the analysis report to compare excursion ON vs OFF behavior
3. tune `z_entry` and `z_exit` first, because they directly control signal timing
4. if too many candidate entries are rejected, relax `atr_ratio_min`
5. if the excursion filter blocks too much, lower `excursion_min` or shorten `excursion_window`
6. compare grouped results rather than focusing on a single best run

Useful heuristics:

- too few trades often means over-filtering
- strong `blocked_by_atr` counts suggest the ATR gate is too restrictive for the symbol/date range
- strong `blocked_by_excursion` counts suggest the displacement requirement is too strict

## 7. Common Pitfalls

### Over-filtering

It is easy to combine:

- strict `z_entry`
- trend filter enabled
- ATR filter enabled
- excursion filter enabled

and end up with very few executed trades.

### Too few trades

A high Sharpe from a tiny number of trades may not be robust. Always inspect:

- `num_trades`
- `entry_signals`
- `executed_trades`
- grouped analysis in `analysis_report.md`

### Misinterpreting Sharpe

Sharpe is useful for ranking, but in this project:

- short runs can produce unstable Sharpe values
- flat or low-activity runs may produce weak signal quality despite acceptable ranking
- total return, drawdown, and diagnostics should be checked together with Sharpe

### Forgetting legacy aliases

The current code still accepts:

- `use_art_filter`
- `art_threshold`
- `blocked_by_art`

but these are compatibility paths. For new experiments, prefer:

- `use_atr_filter`
- `atr_ratio_min`
- `blocked_by_atr`
