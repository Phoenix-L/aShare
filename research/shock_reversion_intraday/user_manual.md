# shock_reversion_intraday — User Manual

**Version:** v0.5.0

## Quick start

Run the strategy from the CLI:

```bash
ashare experiment \
  --strategy shock_reversion_intraday \
  --symbols 000001.SZ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --param excursion_lookback_bars=3,5 \
  --param excursion_threshold=0.01,0.02 \
  --param recovery_frac=0.4,0.6 \
  --param take_profit_pct=0.015,0.02 \
  --param stop_loss_pct=0.01,0.02 \
  --param max_hold_bars=8,16 \
  --param use_shock_score_filter=true,false \
  --param shock_score_min=60 \
  --param shock_score_max=80
```

Use the score filter only when you want to constrain entries by shock quality. If `use_shock_score_filter=true`, the runner expects an explicit `shock_score_min`.

## How the strategy works

1. The strategy computes a rolling intraday maximum close over `excursion_lookback_bars`.
2. It measures downside excursion as:

   ```text
   (close - rolling_max(close, N)) / rolling_max(close, N)
   ```

3. A long signal appears when the excursion is below `-excursion_threshold`.
4. If enabled, the shock-score filter keeps only signals inside the configured score band.
5. The strategy buys a fixed number of shares.
6. The open trade exits on the first condition hit:
   - recovery;
   - take profit;
   - stop loss;
   - max hold.

## Parameter guide

### 1. Signal parameters

- `excursion_lookback_bars`  
  Number of intraday bars used for the rolling maximum anchor.

- `excursion_threshold`  
  Minimum downside excursion needed to trigger a long entry.

- `speed_scale`  
  Scaling constant for the score model's speed component.

- `noise_lookback`  
  Number of bars used when estimating recent noise in the score model.

- `noise_ratio_scale`  
  Scaling constant for the score model's noise penalty.

- `score_weight_depth`  
  Weight assigned to shock depth in the score.

- `score_weight_speed`  
  Weight assigned to shock speed in the score.

- `score_weight_stabilization`  
  Weight assigned to stabilization behavior in the score.

- `score_weight_noise_penalty`  
  Weight assigned to the noise penalty in the score.

### 2. Exit parameters

- `recovery_frac`  
  Fraction of the entry shock that must be recovered for the recovery exit to fire.

- `take_profit_pct`  
  Fixed take-profit percentage above entry.

- `stop_loss_pct`  
  Fixed stop-loss percentage below entry.

- `max_hold_bars`  
  Maximum bars to hold a trade before forcing exit.

Important: profit-taking is **recovery OR take-profit**. The position exits as soon as the first profit target is reached; it does not wait for both profit conditions.

### 3. Score parameters

- `use_shock_score_filter`  
  Enables shock-score-based entry filtering.

- `shock_score_min`  
  Minimum allowed score for entry when the filter is enabled.

- `shock_score_max`  
  Optional maximum allowed score for entry. Useful for excluding overshock trades.

The score is an entry gate only. It does not rank orders and does not currently change exit behavior.

### 4. Execution parameters

- `trade_unit`  
  Fixed order size in shares. Default: **500**.

This strategy does not use full-capital deployment by default, so portfolio returns can differ materially from summed trade returns.

## Example usage patterns

### Baseline excursion scan

```bash
ashare experiment \
  --strategy shock_reversion_intraday \
  --symbols 600519.SH \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --param excursion_lookback_bars=3,5,8 \
  --param excursion_threshold=0.01,0.015,0.02 \
  --param recovery_frac=0.5 \
  --param take_profit_pct=0.02 \
  --param stop_loss_pct=0.02 \
  --param max_hold_bars=12
```

### Score-filtered scan

```bash
ashare experiment \
  --strategy shock_reversion_intraday \
  --symbols 000858.SZ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --param excursion_lookback_bars=3,5 \
  --param excursion_threshold=0.01,0.02 \
  --param use_shock_score_filter=true \
  --param shock_score_min=60,70 \
  --param shock_score_max=80,90 \
  --param recovery_frac=0.4,0.6 \
  --param take_profit_pct=0.015,0.02 \
  --param stop_loss_pct=0.01,0.02 \
  --param max_hold_bars=8,16
```

### Conservative exits

```bash
ashare experiment \
  --strategy shock_reversion_intraday \
  --symbols 002850.SZ \
  --start 2025-07-01 \
  --end 2026-02-28 \
  --param excursion_lookback_bars=20 \
  --param excursion_threshold=0.03,0.05 \
  --param recovery_frac=0.5 \
  --param take_profit_pct=0.05 \
  --param stop_loss_pct=0.05 \
  --param max_hold_bars=40
```

## Outputs

### `trades.csv`

Contains one row per completed trade, including:

- entry / exit datetimes;
- entry / exit prices;
- `pnl_pct`;
- `holding_bars`;
- `mfe_pct`, `mae_pct`, `etd`;
- `anchor_price_at_entry`;
- `excursion_at_entry`;
- `shock_score_at_entry`;
- `exit_reason`.

Use this file when you want to inspect trade quality and execution efficiency.

### `diagnostics_summary.json`

Contains run-level diagnostic aggregates such as:

- `entry_signals`
- `executed_trades`
- `blocked_by_multiple`
- optional score-filter block counts
- `avg_pnl`
- `avg_mfe`
- `avg_mae`
- `avg_etd`
- exit-reason win rates

Use this file to understand signal conversion and the quality of exits.

### `run_performance_report.csv`

This is the final merged report for comparing runs. It combines:

- account-level broker returns;
- trade-level quality metrics;
- diagnostic aggregates;
- parameter settings.

Key columns include:

- `total_return`
- `total_return_simple`
- `total_return_log`
- `sum_trade_return_pct`
- `compound_trade_return_pct`
- `avg_pnl`
- `executed_trades`
- `avg_mfe`
- `avg_mae`
- `avg_etd`
- `avg_shock_score`

## How to interpret key outputs

### `total_return` vs `sum_trade_return_pct`

- `total_return` measures account growth:

  ```text
  (final_equity / initial_cash) - 1
  ```

- `sum_trade_return_pct` measures the sum of trade `pnl_pct` values.

Interpretation:

- high `sum_trade_return_pct` with low `total_return` usually means the signal model is working, but capital utilization is weak because trade size is fixed and cash remains idle;
- if both are weak, the edge itself likely needs improvement.

### `avg_pnl`

`avg_pnl` is the average `pnl_pct` per completed trade.

- positive `avg_pnl` means the average trade makes money in percentage terms;
- low or negative `avg_pnl` suggests the shock threshold or exit settings may be too loose.

### `executed_trades`

`executed_trades` counts completed trades, not raw signals.

Compare it with `entry_signals`:

- if `entry_signals` is high but `executed_trades` is much lower, many signals were blocked by execution state or by the score filter;
- if both are low, the signal threshold may be too strict.

### MFE / MAE / ETD

- high MFE with low realized PnL suggests exit inefficiency;
- large negative MAE suggests entries may be too early or stop losses too loose;
- high ETD means the strategy gave back a lot from the trade peak before exiting.

## Consistency notes

The current strategy implementation:

- uses excursion only;
- does not use trend filters;
- does not use ATR / ART filters;
- does not use z-score logic;
- does not currently implement score-conditioned exits.

## Changelog

### v0.5.0

- added documentation for `sum_trade_return_pct`;
- clarified `total_return`, `total_return_simple`, and `total_return_log` usage;
- removed obsolete references to trend and ATR/ART filters;
- documented the shock-score entry filter;
- corrected exit wording to **recovery OR take-profit**;
- improved output and diagnostics explanations for research workflows.
