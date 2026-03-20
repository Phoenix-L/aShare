# shock_reversion_intraday — System Architecture

**Version:** v0.5.0

## Architecture overview

`shock_reversion_intraday` runs on the shared aShare experiment stack but uses a strategy-specific signal path built entirely from the primary intraday feed.

```text
Provider data -> pandas minute DataFrame -> Backtrader intraday feed
-> ShockReversionIntradayStrategy
-> shared exit engine + broker accounting
-> diagnostics/trade exports
-> run_performance_report.csv
```

## Pipeline

### 1. Data feed

The experiment executor loads intraday minute/30-minute data into pandas and converts it into a Backtrader feed.

For this strategy:

- only `datas[0]` is required;
- there is **no** daily-resampled companion feed;
- warm-up depends on `excursion_lookback_bars` and the score model's minimum bar history.

### 2. Signal generation (excursion)

Inside `ShockReversionIntradayStrategy`:

- `rolling_max_close = Highest(close, period=excursion_lookback_bars)`
- `excursion = (close - rolling_max_close) / rolling_max_close`

The signal is triggered when:

```text
excursion <= -excursion_threshold
```

This is a pure intraday event detector; it is not a z-score and does not depend on ATR or trend state.

### 3. Optional score filter

On each bar, the strategy computes a full shock-score breakdown:

- `depth_score`
- `speed_score`
- `stabilization_score`
- `noise_penalty`
- `shock_score`

If `use_shock_score_filter` is enabled, entry requires:

- `shock_score >= shock_score_min`
- and, if configured, `shock_score <= shock_score_max`

This stage only filters entries. It does not rank signals and does not alter broker sizing.

### 4. Order execution (fixed 500 shares)

When the signal passes all checks and the strategy is flat:

- a buy order is submitted with `size = trade_unit`;
- the default size is **500 shares**;
- execution is fixed-size, not capital-proportional.

At fill time, the strategy freezes the entry context:

- `anchor_price_at_entry`
- `excursion_at_entry`
- `shock_score_at_entry`

These frozen values are later exported into `trades.csv`.

### 5. Exit engine

Open positions are evaluated bar by bar by the shared execution component.

The engine computes:

- `recovery_target`
- `take_profit_price`
- `effective_target_price = min(recovery_target, take_profit_price)` when both exist
- stop-loss threshold from `stop_loss_pct`
- max-hold threshold from `max_hold_bars`

Exit precedence is effectively:

1. stop loss if price is already below the stop threshold;
2. profit exit when the effective target is reached (**recovery OR take-profit**);
3. max hold once `holding_bars >= max_hold_bars`.

The strategy normalizes exit reasons to stable labels:

- `recovery`
- `take_profit`
- `stop_loss`
- `max_hold`

### 6. Broker equity tracking

Backtrader broker state tracks:

- cash;
- marked-to-market portfolio value;
- commission / slippage effects;
- account-level return metrics.

Account performance is extracted after the backtest as:

- `final_value`
- `total_return`
- `total_return_simple`
- `total_return_log`
- `sharpe`
- `max_drawdown`
- `num_trades`

### 7. Diagnostics and reporting

The strategy emits:

- `diagnostics` for per-bar history;
- `signal_events` for threshold-crossing signal rows;
- `completed_trades` for trade-level exports.

The executor persists these into experiment artifacts and the reporting layer merges them into research-ready summaries.

## Metrics pipeline

### `trades.csv` → trade-level metrics

`trades.csv` stores one row per completed trade, including:

- entry / exit timestamps;
- entry / exit prices;
- `pnl_pct`;
- `mfe_pct`, `mae_pct`, `etd`;
- `anchor_price_at_entry`;
- `excursion_at_entry`;
- `shock_score_at_entry`;
- exit reason fields.

This file is the source for trade-level statistics such as:

- `sum_trade_return_pct`
- `compound_trade_return_pct`
- average holding bars
- exit-reason shares
- average shock score at entry

### `diagnostics_summary.json` → aggregated metrics

`diagnostics_summary.json` aggregates bar-level and completed-trade diagnostics, including:

- `total_bars`
- `entry_signals`
- `executed_trades`
- `blocked_by_multiple`
- optional `blocked_by_shock_score_low`
- optional `blocked_by_shock_score_high`
- `avg_pnl`
- `avg_mfe`
- `avg_mae`
- `avg_etd`
- `median_etd`
- `max_etd`
- `mfe_pnl_gap`
- `pnl_capture_ratio`
- `win_rate_by_exit_reason`
- `avg_holding_bars_by_exit_reason`

### `run_performance_report.csv` → final merged report

`run_performance_report.csv` merges:

- account-level metrics from run payloads and broker outputs;
- trade-level metrics from `trades.csv`;
- diagnostic aggregates from `diagnostics_summary.json`;
- selected parameter values from the run configuration.

This file is the best single report for comparing runs because it keeps account-level return and trade-level quality metrics side by side.

## Trade-level vs account-level metrics

The architecture intentionally separates:

### Trade-level metrics

These come from completed trades and measure signal/execution quality:

- `pnl_pct`
- `sum_trade_return_pct`
- `compound_trade_return_pct`
- `avg_pnl`
- `avg_mfe`
- `avg_mae`
- `avg_etd`

### Account-level metrics

These come from broker equity and measure portfolio outcome:

- `final_value`
- `total_return`
- `total_return_simple`
- `total_return_log`
- `max_drawdown`
- `sharpe`

This distinction matters because the strategy does not deploy all capital into each trade.

## Known design decision

The strategy uses **fixed share sizing**, not full capital deployment.

Implications:

- default entries buy 500 shares regardless of account size;
- a profitable signal model can still produce low `total_return` if capital utilization is low;
- `sum_trade_return_pct` is therefore useful as a signal-strength measure that is less distorted by cash drag.

## Components intentionally not present

The current architecture does **not** include:

- trend-filter stage;
- ATR / ART filter stage;
- daily moving-average subsystem;
- score-conditioned exit subsystem.

## Changelog

### v0.5.0

- updated the pipeline description to the current excursion-only strategy;
- removed outdated trend and ATR/ART filter architecture references;
- added the optional shock-score filter stage;
- clarified fixed-share execution and capital-utilization consequences;
- documented the metrics pipeline from `trades.csv` and `diagnostics_summary.json` into `run_performance_report.csv`.
