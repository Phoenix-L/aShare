# shock_reversion_intraday — Strategy

**Version:** v0.5.0

## Overview

`shock_reversion_intraday` is a long-only intraday mean-reversion strategy that buys downside shock events measured from a recent **intraday** rolling maximum close. The strategy does **not** use daily resampling, trend alignment, or ATR gating. It detects a downside excursion, optionally filters that signal with a shock-strength score, then hands the open position to a shared exit engine.

## Strategy behavior

### Signal logic

The locked signal is an intraday downside excursion from a rolling maximum close:

```text
anchor_price = rolling_max(close, N)
excursion = (close - anchor_price) / anchor_price
```

Where:

- `N = excursion_lookback_bars`.
- `rolling_max(close, N)` is computed on the **intraday execution feed**, not on a daily feed.
- `excursion` is typically `<= 0`; more negative values indicate a deeper downside shock.

The entry trigger is:

```text
excursion <= -excursion_threshold
```

This means the strategy enters only after the current close falls far enough below the recent intraday rolling maximum.

### Entry logic

The strategy is **long-only**.

A new long order is submitted only when all of the following are true:

1. the downside excursion trigger fires;
2. there is no current position;
3. there is no active order;
4. if enabled, the shock-score filter passes.

Order size is fixed by `trade_unit`, which defaults to **500 shares**.

## Shock score system

Each entry signal is scored using the shock-strength model. The score is recorded in diagnostics as `shock_score`, and for executed trades the entry snapshot is frozen as:

- `shock_score_at_entry`

### What the score does

The score is an **entry filter only**. It is **not** used to rank signals against each other inside the strategy.

### Optional score filter

The filter is controlled by:

- `use_shock_score_filter`
- `shock_score_min`
- `shock_score_max`

Behavior:

- if `use_shock_score_filter = false`, the score is still computed and exported, but it does not block entry;
- if `use_shock_score_filter = true`, the signal must satisfy:

```text
shock_score >= shock_score_min
```

and, if `shock_score_max` is provided:

```text
shock_score <= shock_score_max
```

Interpretation:

- `shock_score_min` removes weak shocks;
- `shock_score_max` can remove overshock events that are too extreme.

Blocked signals are tracked in diagnostics as `blocked_by_shock_score_low` and `blocked_by_shock_score_high`.

## Exit logic

The strategy uses the shared exit engine with four independent exit paths:

1. **recovery-based exit**
2. **take profit**
3. **stop loss**
4. **max hold**

### Recovery-based exit

At entry, the strategy freezes the rolling anchor price and uses it for the life of the trade:

```text
recovery_target = entry_price + recovery_frac * (anchor_price_at_entry - entry_price)
```

This anchor is **applied at entry and frozen**. It does not float upward or recalculate after the trade is open.

### Take profit

```text
take_profit_price = entry_price * (1 + take_profit_pct)
```

### Stop loss

```text
stop_price = entry_price * (1 - stop_loss_pct)
```

### Max hold

The trade exits once:

```text
holding_bars >= max_hold_bars
```

### Critical profit-exit rule

Profit exits are evaluated as:

**recovery OR take-profit**

—not a requirement to hit both profit conditions together.

Implementation detail:

- the engine computes both the recovery target and take-profit target;
- if both exist, it uses the **earlier/easier target**;
- the trade exits when the **first condition hit** triggers an exit.

In practice, the effective profit target is:

```text
effective_target_price = min(recovery_target, take_profit_price)
```

So the position closes on the earliest profit objective, while stop-loss and max-hold remain independent safeguards.

## Score-conditioned exit

**Current status:** not implemented in the live strategy logic.

The reporting layer exposes a placeholder field named `use_score_conditioned_exit`, but the current `shock_reversion_intraday` implementation does **not** switch exit parameters by score band. Exit parameters are shared across trades and come directly from the configured values:

- `recovery_frac`
- `take_profit_pct`
- `stop_loss_pct`
- `max_hold_bars`

Accordingly:

- there is no active score-band exit matrix in the strategy;
- no exit parameters are dynamically changed by score after entry.

## Removed components

The current strategy intentionally has:

- **NO trend filter**
- **NO ATR / ART filter**
- **NO daily moving-average dependency**
- **NO z-score signal path**

Legacy parameters such as `use_trend_filter`, `trend_ma_period`, `use_atr_filter`, `use_art_filter`, `atr_ratio_min`, `art_threshold`, `z_entry`, and `z_exit` are rejected by validation.

## Trading workflow summary

1. Read the current intraday bar.
2. Compute `rolling_max(close, excursion_lookback_bars)`.
3. Compute `excursion`.
4. Compute the shock score and score breakdown.
5. Mark a signal when `excursion <= -excursion_threshold`.
6. If the optional score filter is enabled, require the score to pass `shock_score_min` / `shock_score_max`.
7. If flat and eligible, submit a fixed-size buy order.
8. Freeze `anchor_price_at_entry`, `excursion_at_entry`, and `shock_score_at_entry` when the entry fills.
9. While in position, evaluate recovery, take-profit, stop-loss, and max-hold on every bar.
10. Exit on the first exit condition hit.

## Parameters

| Parameter | Purpose |
| --- | --- |
| `trade_unit` | Fixed share size per entry order. Default: 500 shares. |
| `excursion_lookback_bars` | Intraday rolling window used to compute the anchor price. |
| `excursion_threshold` | Minimum downside excursion needed to trigger a signal. |
| `take_profit_pct` | Fixed take-profit distance above entry. |
| `recovery_frac` | Fraction of the entry shock that must be recovered to trigger the recovery exit. |
| `max_hold_bars` | Maximum holding period in intraday bars. |
| `stop_loss_pct` | Fixed stop-loss distance below entry. |
| `speed_scale` | Scale factor used in the shock score speed component. |
| `noise_lookback` | Number of recent bars used to estimate noise in the score model. |
| `noise_ratio_scale` | Scale factor for the score noise penalty. |
| `score_weight_depth` | Weight of shock depth in the score. |
| `score_weight_speed` | Weight of shock speed in the score. |
| `score_weight_stabilization` | Weight of stabilization behavior in the score. |
| `score_weight_noise_penalty` | Weight of the noise penalty in the score. |
| `use_shock_score_filter` | Enables score-based entry filtering. |
| `shock_score_min` | Lower score bound when the filter is enabled. |
| `shock_score_max` | Optional upper score bound when the filter is enabled. |

## Performance Metrics

### 1. `total_return` (account-level)

Definition:

```text
(final_equity / initial_cash) - 1
```

This is an **account-level** result. It includes:

- fixed position sizing;
- commission and transaction costs handled by the broker;
- cash drag from uninvested capital.

Because the strategy trades a fixed number of shares instead of fully deploying capital, `total_return` can remain modest even when trade-level edge is strong.

### 2. `sum_trade_return_pct` (trade-level, new)

Definition:

```text
sum of pnl_pct across all completed trades
```

Purpose:

- measures aggregated signal strength independent of account sizing;
- helps separate strategy edge from capital deployment efficiency.

### 3. `avg_pnl`

`avg_pnl` is the **average `pnl_pct` per trade**, expressed as a percentage.

It is **not** absolute price PnL and **not** currency PnL.

### 4. `compound_trade_return_pct`

If present in reporting, it is defined as:

```text
product(1 + pnl_pct / 100) - 1
```

In exported reports, this value is presented in **percent space**, i.e. the compounded trade return multiplied by 100.

### 5. MFE / MAE / ETD

- **MFE**: max favorable move during the trade.
- **MAE**: max adverse move during the trade.
- **ETD**: end-trade giveback from the trade peak.

For this strategy, ETD is recorded as:

```text
(mfe_price - exit_price) / entry_price
```

How to use them:

- **entry quality**: high MFE with acceptable MAE suggests the entry captures strong rebounds;
- **exit efficiency**: low realized PnL relative to MFE suggests profits are being given back before exit.

### 6. Key interpretation guidance

- **high `sum_trade_return_pct` + low `total_return`**  
  → the signals may be good, but capital utilization is weak because the strategy uses fixed-size trades and leaves much cash idle.

- **high MFE vs low realized PnL**  
  → exit logic may be inefficient, often visible through high ETD or a low PnL capture ratio.

## Changelog

### v0.5.0

- added `sum_trade_return_pct` documentation;
- clarified account-level vs trade-level return definitions;
- removed outdated trend-filter and ATR/ART-filter references;
- documented the shock score entry filter (`use_shock_score_filter`, `shock_score_min`, `shock_score_max`);
- clarified that profit exits are **recovery OR take-profit**;
- improved diagnostics and trade-efficiency metric explanations.
