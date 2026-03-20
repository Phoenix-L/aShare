# shock_reversion_intraday — System Architecture

## End-to-end data flow

`shock_reversion_intraday` uses the same shared engine as `mean_reversion_advanced`:

```text
Tushare (or the configured provider) -> pandas loader/cache -> Backtrader feed
-> ShockReversionIntradayStrategy -> diagnostics/trades
```

That means the same CLI, experiment runner, metrics extraction, and artifact-writing pipeline is reused unchanged.

## Feed structure

The strategy operates only on the primary intraday feed:

- `datas[0]`: primary intraday execution feed.

Unlike `mean_reversion_advanced`, this strategy does not depend on a daily-resampled feed or moving-average state.

## Indicator wiring

Indicator construction is strategy-specific:

- `rolling_max_close` is `Highest(self.data.close, period=excursion_lookback_bars)` on the intraday feed;
- `excursion = (close - rolling_max_close) / rolling_max_close` is computed directly from the intraday feed.

This makes excursion a pure intraday event signal rather than a z-score, ATR-normalized mean-distance signal, or trend-filtered setup.

## Execution flow

The runtime loop is centered on `next()`.

1. Read the intraday close, rolling anchor, and excursion.
2. Skip bars until the rolling lookback is ready.
3. Compute the entry trigger: `excursion <= -excursion_threshold`.
4. Evaluate the shared exit engine using the frozen entry anchor and current price.
5. If a position is open and any exit rule fires, submit a close order.
6. If flat and the excursion trigger fires, submit a buy order.
7. Append per-bar diagnostics and, when applicable, signal-event exports.

## Exit engine

The strategy reuses the shared execution helpers from `components/execution.py`.

The exit engine evaluates:

- recovery target;
- take-profit target;
- stop-loss threshold;
- maximum holding bars.

The resulting decision is normalized into stable exit labels:

- `recovery`
- `take_profit`
- `stop_loss`
- `max_hold`

## Diagnostics integration

The strategy is fully integrated with the shared diagnostics pipeline.

### Signal tracking

Every qualifying entry signal can also be exported through `signal_events`, including:

- symbol
- datetime
- excursion
- threshold
- whether the signal executed

### Bar diagnostics

Per-bar diagnostics include:

- `signal_trigger`
- `excursion`
- `entry_signal`
- `executed`
- `holding_bars`
- recovery / take-profit targets
- normalized exit reason

### Diagnostics summary

Because the strategy is filter-independent, its `diagnostics_summary.json` includes only:

- `total_bars`
- `entry_signals`
- `executed_trades`
- `blocked_by_excursion`
- `blocked_by_multiple`
- trade-efficiency metrics such as MFE / MAE / ETD

### Trade records

Completed trades capture:

- entry and exit timestamps;
- entry and exit prices;
- anchor price at entry;
- excursion at entry;
- MFE/MAE metrics plus ETD;
- exit reason and holding time.

## Experiment runner integration

The strategy uses the same experiment stack as `mean_reversion_advanced`.

### Grid search

`execute_experiment_spec()` expands the parameter grid, validates each combination, runs the backtests, and writes shared experiment outputs.

### Deduplication

`generate_parameter_sets()` and `deduplicate_parameter_sets()` normalize shock-reversion parameter combinations so that only meaningful excursion and exit dimensions are retained before execution.
