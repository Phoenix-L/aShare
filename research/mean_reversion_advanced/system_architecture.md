# mean_reversion_advanced — System Architecture

## End-to-end data flow

The strategy runs inside the shared aShare experiment stack:

```text
Tushare (or the configured provider) -> pandas loader/cache -> Backtrader feed
-> daily resample -> MeanReversionAdvanced -> diagnostics/trade artifacts
```

When the environment is configured for Tushare, the practical flow is:

1. the provider factory resolves `TushareProvider`;
2. `load_minute_30()` fetches intraday OHLCV + turnover data into pandas;
3. `to_backtrader_feed()` converts the normalized frame into a Backtrader feed;
4. `run_backtest()` also creates a 1-day resampled view of the same feed;
5. `MeanReversionAdvanced` consumes both feeds;
6. diagnostics and summary artifacts are written by the runner and experiment executor.

## Feed structure

The strategy depends on two synchronized feeds:

- `datas[0]`: the primary intraday execution feed;
- `datas[1]`: a 1-day resampled feed used for daily moving averages.

This split is important because the strategy trades intraday bars while interpreting `MA20` and `MA120` as trading-day statistics rather than intraday-bar statistics.

## Indicator wiring

Indicator construction is split between shared helpers and strategy-local wiring.

### Shared helper indicators

`build_mean_reversion_indicators()` wires:

- `MA20` from the daily-resampled feed;
- `MA120` from the daily-resampled feed;
- `ATR14` from the intraday execution feed.

### Strategy-local indicators

Inside `MeanReversionAdvanced.__init__()`:

- `self.ma20`, `self.ma120`, and `self.atr14` are created through the shared helper;
- `self.atr3 = ATR(period=3)` is created directly on the intraday feed for the ATR ratio filter.

## Execution flow

The runtime loop is centered on `next()`.

1. Read the current close and indicator values.
2. Skip the bar if ATR or required MA inputs are not ready.
3. Compute:
   - `zscore = (close - MA20) / ATR14`
   - `atr_ratio = ATR3 / close`
4. Determine the entry trigger: `zscore <= z_entry`.
5. Determine the exit trigger: `zscore >= z_exit`.
6. If a position is open, update trade state metrics first.
7. If an open position also satisfies the exit trigger, send a close order and record trade diagnostics.
8. If flat, evaluate the trend filter and ATR filter.
9. If the signal and both filters pass, submit a buy order with `trade_unit` shares.
10. Append a per-bar diagnostics row regardless of whether the signal executed.

## Diagnostics model

The strategy emits diagnostics through `self.diagnostics` and `self.trade_diagnostics`.

### Per-bar diagnostics

Each processed bar records fields such as:

- `datetime`
- `zscore`
- `signal_trigger`
- `trend_ok`
- `atr_filter_active`
- `atr_ok`
- `atr_ratio`
- `entry_signal`
- `executed`
- `blocked_by`
- `holding_bars`

### Blocked reasons

When an entry signal fires but cannot execute, the strategy records stable block labels, including:

- `trend_filter`
- `atr_filter`

### Trade lifecycle diagnostics

For completed trades, the strategy stores:

- entry context, including z-score and filter state at entry;
- exit context, including exit-bar z-score, holding bars, and realized PnL;
- execution-quality statistics exported from the shared position state helpers.

## Experiment runner integration

The strategy uses the standard experiment pipeline.

### Grid search

`execute_experiment_spec()`:

1. loads base parameters from the YAML spec;
2. expands `grid_search` into a Cartesian product;
3. validates parameters;
4. runs one backtest per symbol/parameter set;
5. writes run artifacts and experiment summaries.

### Deduplication

`generate_parameter_sets()` normalizes parameter combinations before execution so equivalent runs are not duplicated. This keeps the experiment count stable when repeated or redundant combinations would otherwise produce the same effective run configuration.

## Output artifacts

The runner and executor write a consistent artifact set, including:

- `metrics.json`
- `diagnostics.json`
- `diagnostics_summary.json`
- `config_snapshot.yaml`
- `run_result.json`
- experiment-level `summary.csv` and `summary_sorted.csv`

These artifacts support both CLI inspection and downstream research analysis.
