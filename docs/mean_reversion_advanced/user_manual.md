# User Manual — mean_reversion_advanced

## 1. Quick Start

Run the shipped experiment spec:

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

This launches a parameter sweep for `mean_reversion_advanced`, writes run artifacts under `outputs/mean_reversion_advanced_demo/`, and creates experiment-level summary CSV files.

## 2. Key Parameters

### `signal_mode`

Selects the primary entry signal.

- `"zscore"`: default; use the ATR-normalized z-score trigger
- `"excursion"`: use the close-based downside excursion trigger

### `z_entry`

Entry threshold for the ATR-normalized z-score.

- more negative values make entries rarer
- less negative values make the strategy react sooner
- used only when `signal_mode="zscore"`

### `z_exit`

Exit threshold for the same z-score.

- lower values exit earlier
- higher values hold longer waiting for more mean reversion
- used only when `signal_mode="zscore"`

### `excursion_lookback_bars`

Lookback used by the close-based excursion signal.

Definition:

- `rolling_max_close = highest(close, excursion_lookback_bars)`
- `excursion = (close - rolling_max_close) / rolling_max_close`

Current behavior:

- uses the intraday execution feed (`self.data.close`)
- only affects entry triggering when `signal_mode="excursion"`

### `excursion_threshold`

Absolute downside threshold for the close-based excursion signal.

- an entry signal fires when `excursion <= -excursion_threshold`
- larger values require a deeper pullback from the recent rolling close high
- smaller values react sooner to shallow dips

### `excursion_lookback_bars`

Lookback used by the close-based excursion signal.

Definition:

- `rolling_max_close = highest(close, excursion_lookback_bars)`
- `excursion = (close - rolling_max_close) / rolling_max_close`

Current behavior:

- uses the intraday execution feed (`self.data.close`)
- only affects entry triggering when `signal_mode="excursion"`

### `excursion_threshold`

Absolute downside threshold for the close-based excursion signal.

- an entry signal fires when `excursion <= -excursion_threshold`
- larger values require a deeper pullback from the recent rolling close high
- smaller values react sooner to shallow dips

### `use_atr_filter`

Enables the ATR ratio filter.

Current effective behavior:

- the filter uses a 3-bar ATR ratio (`ATR3 / close`) rather than the 14-bar ATR used in the z-score
- if omitted, ATR filtering is enabled by default
- legacy `use_art_filter` is still accepted, but deprecated
- the ATR gate is bypassed automatically when `signal_mode="excursion"`

### `atr_ratio_min`

Minimum ATR ratio required for the ATR filter to pass.

Definition:

- `ATR Ratio = ATR3 / Price`

Current effective default:

- `0.02` if neither `atr_ratio_min` nor legacy `art_threshold` is provided

### `use_multi_day_excursion`

Turns the excursion filter on or off.

- `false`: ignore legacy excursion gating
- `true`: require sufficient rolling displacement before entry when `signal_mode="zscore"`

### `excursion_min`

Minimum excursion ratio required when the legacy excursion filter is enabled.

- higher values are more restrictive
- lower values allow more candidate reversals through

### `excursion_window`

Lookback window used to compute the rolling high-low excursion ratio used by the legacy excursion filter.

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

Example that switches the primary signal to excursion mode:

```bash
ashare experiment \
  configs/experiments/mean_reversion_advanced.yaml \
  --param signal_mode=excursion \
  --param excursion_lookback_bars=3,5 \
  --param excursion_threshold=0.01,0.02
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

- `signal_mode`
- `z_entry`
- `z_exit`
- `use_trend_filter`
- `use_atr_filter`
- `use_art_filter` *(legacy alias column retained for compatibility)*
- `use_multi_day_excursion`
- `excursion_lookback_bars`
- `excursion_threshold`
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
2. decide whether the run should be driven by `signal_mode=zscore` or `signal_mode=excursion`
3. if using z-score mode, tune `z_entry` and `z_exit` first, because they directly control signal timing
4. if using excursion mode, tune `excursion_lookback_bars` and `excursion_threshold` first
5. if too many candidate entries are rejected, relax `atr_ratio_min`
6. if the legacy excursion filter blocks too much in z-score mode, lower `excursion_min` or shorten `excursion_window`
7. compare grouped results rather than focusing on a single best run

Useful heuristics:

- too few trades often means over-filtering
- strong `blocked_by_atr` counts suggest the ATR gate is too restrictive for the symbol/date range
- strong `blocked_by_excursion` counts suggest the legacy displacement requirement is too strict in z-score mode
- in `signal_mode="excursion"`, `blocked_by_atr` should normally remain at zero because the ATR gate is bypassed

## 7. Common Pitfalls

### Over-filtering

It is easy to combine:

- strict `z_entry`
- or a large `excursion_threshold`
- trend filter enabled
- ATR filter enabled
- legacy excursion filter enabled

and end up with very few executed trades.

### Too few trades

A high Sharpe from a tiny number of trades may not be robust. Always inspect:

- `num_trades`
- `entry_signals`
- `executed_trades`
- `signal_mode`
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
