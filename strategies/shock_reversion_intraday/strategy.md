# Strategy: shock_reversion_intraday

## Conceptual model

`shock_reversion_intraday` is an **event-driven mean reversion** strategy:

1. Detect downside shock events from close-vs-anchor excursion.
2. Enter only when entry conditions pass.
3. Optionally add ladder legs while price continues lower under controlled spacing.
4. Exit with shared execution rules (recovery / take-profit / stop-loss / time stop).

## Signal and scoring model

Per bar, strategy computes:

- `anchor = rolling_max(close, excursion_lookback_bars)`
- `excursion = (close - anchor) / anchor`
- `signal_trigger = excursion <= -excursion_threshold`

Shock components are shared, then two weighted scores are derived from the same components:

- `entry_shock_score`: used for initial-entry filter only
- `add_shock_score`: used for ladder-add filter only

This separation allows different weight sets for entry and add decisions.

## Entry logic (initial leg)

### Why this exists

Raw excursion catches many events; score filtering helps prioritize cleaner shocks and avoid weaker setups.

### Rules

Entry requires all of the following:

1. `signal_trigger` is true.
2. Flat account (`not self.position`) and no pending order.
3. Entry shock-score filter passes **when enabled**:
   - enabled if any of:
     - `use_shock_score_filter = true`
     - `entry_shock_score_min` set
     - `entry_shock_score_max` set
   - effective bounds:
     - min: `entry_shock_score_min` else legacy `shock_score_min`
     - max: `entry_shock_score_max` else legacy `shock_score_max` else `100`
   - validation: bounds must be within `[0, 100]` and `min <= max`.

If executed, a buy order is submitted for `trade_unit`.

## Ladder logic (add legs)

### Why this exists

This is **not naive averaging down**. Adds are allowed only when continuation is meaningful and controlled by price displacement, signal quality, and spacing constraints.

### Rules

Ladder adds are evaluated only while a live trade is open. Add execution requires:

1. `enable_ladder = true`
2. `leg_count < max_legs`
3. Last leg metadata exists (`last_leg_price`, `last_leg_bar`)
4. Price drop condition from last leg:
   - `close <= last_leg_price * (1 - ladder_min_drop_pct)`
5. Time spacing:
   - `bars_since_last_leg >= ladder_min_bars_between_legs`
6. Score gate:
   - `add_shock_score >= add_score_min`
   - where effective `add_score_min = add_score_min if set else ladder_score_min_add`
7. Remaining hold window:
   - `max_hold_bars - bars_held >= min_bars_left_for_add`
8. No active pending order.

If all pass, strategy buys one additional `trade_unit` leg.

## Exit logic (shared execution engine)

### Why this exists

Exits are unified so stop, profit, and time logic stay consistent across strategy paths. **Recovery is based on anchor, NOT entry price.**

### Rules

Exit conditions are evaluated by shared helper `evaluate_exit_engine` using:

- current close
- current trade state (`avg_entry_price`, `effective_anchor_price`, `lowest_price_since_entry`, `bars_held`)
- configured parameters

1. **Stop loss**
   - `close <= avg_entry_price * (1 - stop_loss_pct)`
2. **Profit target (earliest of two)**
   - Recovery target (anchor-based):
     - `recovery_target = low_watermark + recovery_frac * (effective_anchor_price - low_watermark)`
   - Take profit target:
     - `take_profit_price = avg_entry_price * (1 + take_profit_pct)`
   - Effective target is `min(recovery_target, take_profit_price)` when both exist.
   - Exit subtype:
     - `take_profit` if take-profit is the active earliest target
     - otherwise `anchor_recovery` (exported as `recovery`)
3. **Time stop**
   - `bars_held >= max_hold_bars`

Priority is stop-loss first, then effective profit target, then max-hold.

## Trade state model

Live position state tracks:

- `leg_count`
- `leg_prices`, `leg_sizes`
- `total_size`, `avg_entry_price`
- `last_leg_bar`, `last_leg_price`
- `lowest_price_since_entry`
- `effective_anchor_price`
- `entry_shock_score`
- `add_shock_scores` (list)
- `ladder_used`

One-line insight:

- `add_shock_scores` enables per-leg ladder quality analysis.

Anchor handling:

- On first fill, `effective_anchor_price = anchor_price_at_entry`.
- On add fills, `effective_anchor_price = max(previous_effective_anchor_price, add_leg_anchor)`.
- Recovery exits always reference this effective anchor + low watermark (not raw first-entry price).

## Signal logging fields

For each triggered signal event, exported fields include:

- `entry_executed`
- `add_executed`
- `execution_type` (`"entry"`, `"add"`, or empty)
- `drop_from_last_leg_pct`
- `bars_since_last_leg`

Also includes score diagnostics (`entry_shock_score`, `add_shock_score`, bounds, pass/block flags).

## Key parameter groups

### Entry trigger and score

- `excursion_lookback_bars`
- `excursion_threshold`
- `use_shock_score_filter`
- `entry_shock_score_min`, `entry_shock_score_max`
- legacy fallback: `shock_score_min`, `shock_score_max`
- entry score weights (`entry_score_weight_*`)

### Ladder / adds

- `enable_ladder`
- `max_legs`
- `ladder_min_drop_pct`
- `ladder_min_bars_between_legs`
- `add_score_min` (or fallback `ladder_score_min_add`)
- `min_bars_left_for_add`
- add score weights (`add_score_weight_*`)

### Exits

- `recovery_frac`
- `take_profit_pct`
- `stop_loss_pct`
- `max_hold_bars`

### Cost / sizing

- `trade_unit`
- `use_margin`
- `margin_rate_annual`
- `bars_per_day`
