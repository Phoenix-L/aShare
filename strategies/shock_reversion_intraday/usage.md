# Usage: shock_reversion_intraday

## Run an experiment

Template config:

```bash
ashare experiment configs/experiments/shock_reversion_intraday_template.yaml
```

Ladder-enabled example config:

```bash
ashare experiment configs/experiments/shock_reversion_intraday_ladder_v2.yaml
```

## YAML structure

Minimal structure:

```yaml
strategy: shock_reversion_intraday
symbols: ["002850.SZ"]
start: "2025-07-01"
end: "2026-02-28"
parameters:
  trade_unit: 500
  excursion_lookback_bars: 3
  excursion_threshold: 0.01
  recovery_frac: 0.5
  take_profit_pct: 0.02
  stop_loss_pct: 0.02
  max_hold_bars: 16
  use_shock_score_filter: true
  entry_shock_score_min: 60
  entry_shock_score_max: 100
  enable_ladder: true
  max_legs: 3
  ladder_min_drop_pct: 0.02
  ladder_min_bars_between_legs: 1
  add_score_min: 55
  min_bars_left_for_add: 1
```

### Parameter mapping notes

- Entry score filter uses `entry_shock_score_min/max` (with fallback to legacy `shock_score_min/max`).
- Add score gate uses `add_score_min` (fallback to `ladder_score_min_add`).
- Entry and add can have separate score weights via `entry_score_weight_*` and `add_score_weight_*`.

## How to interpret outputs

### `signals.csv`

Use this to inspect signal quality and execution decisions.

Key columns:

- `entry_shock_score`, `add_shock_score`
- `entry_shock_score_min`, `entry_shock_score_max`
- `entry_executed`, `add_executed`, `execution_type`
- `drop_from_last_leg_pct`, `bars_since_last_leg`
- block flags (`blocked_by_shock_score_low/high`)

### `trades.csv`

Use this to inspect completed trade lifecycle.

Key columns:

- state: `leg_count`, `ladder_used`, `add_shock_scores`, `add_score_count`
- anchor/targets: `anchor_price_at_entry`, `effective_anchor_price`, `recovery_target`, `take_profit_price`, `effective_target_price`
- outcomes: `exit_reason`, `trade_return`, `trade_pnl_amount`, `trade_pnl_net`, `mfe`, `mae`, `etd`

## Validation checklist after a run

1. Confirm `signals.csv` includes ladder execution fields and score bounds.
2. Confirm `trades.csv` includes `add_shock_scores` and does **not** depend on removed aggregate add-score fields.
3. Confirm exit reasons align with configured exit controls (`recovery`, `take_profit`, `stop_loss`, `max_hold`).
