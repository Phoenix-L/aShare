# aShare User Manual (Practical)

## 1) Setup

### Install
```bash
pip install -e .
```

### Optional provider selection
Default provider is BaoStock.

Use Tushare explicitly:
```bash
export ASHARE_DATA_PROVIDER=tushare
export TUSHARE_TOKEN=<your_token>
```

## 2) Run your first backtest

```bash
ashare backtest \
  --symbol 000001.SZ \
  --strategy mean_reversion_advanced \
  --start 2025-01-01 \
  --end 2025-12-31
```

Notes:
- `--start` and `--end` must be strict `YYYY-MM-DD`.
- If no data is returned for the symbol/range, command exits with error.

## 3) Run an experiment (YAML mode, recommended)

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

This mode:
- loads experiment spec,
- applies optional CLI overrides,
- runs all symbol × parameter combinations,
- writes per-run artifacts under `outputs/<experiment_name>/`.

## 4) Grid search usage

Example YAML:
```yaml
experiment_name: mean_reversion_advanced_demo
strategy: mean_reversion_advanced
symbols: [002850.SZ]
date_range:
  start: 2025-07-01
  end: 2026-02-28
parameters:
  trade_unit: 500
  use_trend_filter: true
  use_art_filter: true
grid_search:
  z_entry: [-1.2, -1.5, -1.8]
  z_exit: [0.3, 0.5]
```

Run count = `len(symbols) * len(z_entry) * len(z_exit)`.
For the example above: `1 * 3 * 2 = 6` runs.

## 5) CLI overrides (`--start`, `--end`, `--param`)

### Override date range
```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml \
  --start 2025-01-01 \
  --end 2025-12-31
```

### Override parameters
Single value => base parameter override:
```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml \
  --param trade_unit=1000
```

Multiple values => grid override:
```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml \
  --param z_entry=-1.0,-1.3,-1.6 \
  --param z_exit=0.3,0.5
```

### Real command example requested
```bash
ashare experiment config.yaml \
  --start 2025-01-01 \
  --end 2025-12-31
```

## 6) Understanding outputs

## A) YAML experiment outputs (`outputs/<experiment_name>/`)

### `metrics.json`
Per-run metrics from analyzers, including:
- `final_value`
- `rtot` / `total_return`
- `sharpe`
- `max_drawdown`
- `max_drawdown_len`
- `num_trades`

### `config_snapshot.yaml`
Per-run snapshot including:
- `strategy`
- concrete `parameters` used in that run
- `symbol`
- effective `date_range` (after CLI override if any)

### `summary.csv` and `summary_sorted.csv`
Built after experiment completion.
- `summary.csv`: raw run collection order.
- `summary_sorted.csv`: ranked by sharpe desc, return desc, drawdown asc.

## B) Direct CLI experiment mode outputs (`experiments/experiment_<timestamp>/`)
- `results.csv`
- `config.json`

This path does not currently generate the `outputs/<experiment_name>/summary.csv` structure.

## 7) Strategy parameters (mean_reversion_advanced)

- `trade_unit` (default `500`): order size on entry.
- `z_entry` (default `-1.5`): entry threshold for z-score.
- `z_exit` (default `0.5`): exit threshold for z-score.
- `use_trend_filter` (default `true`): requires `close > ma120` to allow entry.
- `use_art_filter` (default `true`): requires `ART >= 0.02` to allow entry.

Tip:
- If no trades occur, test with looser thresholds or disable one filter to diagnose trade starvation.
