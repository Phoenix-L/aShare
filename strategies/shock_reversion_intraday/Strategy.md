# shock_reversion_intraday — Strategy

**Version:** v0.6.0

## Overview

`shock_reversion_intraday` is a long-only, shock-based mean reversion strategy. It looks for short-term downside dislocations from a recent intraday close anchor, optionally filters those dislocations with a shock-strength score, and exits through a small, explicit set of recovery and risk controls.

## Entry Logic

### 1. Excursion trigger

The primary signal is the intraday excursion:

- anchor = rolling maximum close over `excursion_lookback_bars`
- excursion = `(close - anchor) / anchor`
- a long setup is eligible when excursion is less than or equal to `-excursion_threshold`

This keeps entry logic event-driven and independent from daily trend or ATR gates.

### 2. Optional shock score filter

When `use_shock_score_filter: true`, an eligible excursion must also pass:

- `shock_score >= shock_score_min`
- `shock_score <= shock_score_max` when an upper bound is configured

The score is used only as a selection filter. It does not currently switch to different exit rules by score bucket.

## Exit Logic

A filled position is managed by four exit controls:

- `recovery_frac`: exit when price recovers a configured fraction of the shock depth from the entry anchor
- `take_profit_pct`: fixed profit target from entry price
- `stop_loss_pct`: fixed downside stop from entry price
- `max_hold_bars`: time stop measured in intraday bars

When both recovery and take-profit are active, the effective profit exit is the first target reached.

## Metric Definitions

All return and drawdown metrics are stored as **decimal ratios**, not percentage strings.

- `trade_return`: `(exit_price - entry_price) / entry_price`
- `sum_trade_return`: arithmetic sum of all completed `trade_return` values
- `compound_trade_return`: compounded trade-level return, `Π(1 + trade_return) - 1`
- `total_return_simple`: portfolio return from equity change, `(final_equity - initial_equity) / initial_equity`
- `total_return_log`: log portfolio return, `ln(final_equity / initial_equity)`
- `mfe`: maximum favorable excursion from entry, as a decimal ratio
- `mae`: maximum adverse excursion from entry, as a decimal ratio
- `etd`: end-trade drawdown from the trade's best unrealized price to the actual exit, scaled by entry price

Interpretation notes:

- `sum_trade_return` measures signal-level trade outcome accumulation.
- `compound_trade_return` shows what trade outcomes imply when chained without cash drag.
- `total_return_simple` reflects actual portfolio equity movement and therefore includes idle cash, position sizing, and financing effects.

## Known Limitations

- No ladder or pyramiding logic yet.
- `trade_unit` remains fixed per run.
- Capital efficiency is still below the theoretical trade-return path because unused cash can remain idle between trades.
