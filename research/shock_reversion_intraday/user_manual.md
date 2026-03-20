# shock_reversion_intraday — User Manual

## Quick start

Run the strategy directly from the CLI:

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
  --param max_hold_bars=8,16
```

## Parameter guide

`shock_reversion_intraday` is a pure event-driven strategy. Entries depend only on the intraday excursion signal and not on any moving-average or trend gate.

### Entry parameters

- `excursion_lookback_bars`: controls the rolling anchor window.
- `excursion_threshold`: minimum downside excursion required to trigger entry.

### Exit parameters

- `recovery_frac`: fraction of the shock that must be recovered for the recovery exit.
- `take_profit_pct`: fixed take-profit percentage above entry.
- `stop_loss_pct`: fixed maximum tolerated loss below entry.
- `max_hold_bars`: maximum holding duration in bars.

### Sizing

- `trade_unit`: fixed share count used for each entry.

## Tuning guidance

### `excursion_threshold`

- increasing `excursion_threshold` usually produces fewer trades with stronger shock quality;
- decreasing it usually increases frequency but can let ordinary noise qualify as a signal.

### `recovery_frac`

- increasing `recovery_frac` makes the recovery exit harder to hit and tends to hold trades longer;
- decreasing it makes profit capture easier but may exit too early on larger rebounds.

### `take_profit_pct` and `max_hold_bars`

- lower `take_profit_pct` values monetize smaller rebounds faster;
- lower `max_hold_bars` values enforce faster capital recycling but can truncate slower recoveries.

## Output interpretation

After the run, inspect:

- `signals.csv` for all shock events that crossed the threshold;
- `trades.csv` for completed trade records, ETD, and exit reasons;
- `diagnostics_summary.json` for signal conversion and exit-efficiency metrics;
- `summary_sorted.csv` for top parameter combinations.

## Recommended workflow

1. tune `excursion_threshold` first;
2. then tune `recovery_frac` versus `take_profit_pct`;
3. only after that, tighten `stop_loss_pct` and `max_hold_bars` to shape risk and holding time.
