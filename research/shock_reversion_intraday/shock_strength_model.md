# shock_reversion_intraday — Shock Strength Model v1

## Objective

Design an interpretable, strategy-local score that ranks downside shock events before any laddering, pyramiding, dynamic sizing, or cross-symbol ranking is introduced.

The score is intended to improve signal selection quality for `shock_reversion_intraday` by favoring deeper, faster downside shocks that show early stabilization while de-emphasizing moves that look small relative to recent bar-to-bar noise.

## Scope

- Applies only to `shock_reversion_intraday`.
- Uses only the current intraday feed.
- No machine learning.
- No dynamic sizing.
- No ladder or pyramid logic.
- No multi-symbol ranking in v1.

## Locked v1 feature definitions

### 1. Depth score

```text
excursion = (close - rolling_max(close, N)) / rolling_max(close, N)
depth_raw = abs(excursion)
depth_score = clip(depth_raw / (2 * excursion_threshold), 0, 1)
```

Interpretation: deeper downside shocks should generally receive a higher score.

### 2. Speed score

```text
speed_ret = (close[0] - close[-2]) / close[-2]
speed_scale = 0.03
speed_score = clip(abs(min(speed_ret, 0)) / speed_scale, 0, 1)
```

Interpretation: sharper two-bar downside moves score higher than slow drifts.

### 3. Stabilization score

Start at `0.0`.

Add `0.5` if:

```text
close[0] > close[-1]
```

Define:

```text
close_location = (close - low) / (high - low + eps)
```

Add `0.5` if:

```text
close_location >= 0.5
```

Final score is one of `{0.0, 0.5, 1.0}`.

Interpretation: the signal bar should show at least some evidence that selling pressure is stabilizing.

### 4. Noise penalty

```text
noise_lookback = 10
noise_base = mean(abs(ret_1bar), over last 10 bars)
noise_ratio = depth_raw / (noise_base + eps)
noise_ratio_scale = 3.0
noise_penalty = 1 - clip(noise_ratio / noise_ratio_scale, 0, 1)
```

Interpretation: shocks that are large relative to recent noise should incur less penalty; ordinary fluctuations should incur more.

## Locked v1 score formula

```text
shock_score = 100 * (
    0.45 * depth_score +
    0.25 * speed_score +
    0.20 * stabilization_score -
    0.10 * noise_penalty
)
```

Then clip to `[0, 100]`.

## Interpretation bands

- `< 40`: weak
- `40–60`: moderate
- `60–80`: strong
- `> 80`: exceptional

## Default parameters

- `excursion_lookback_bars = 3` (existing strategy default)
- `excursion_threshold = 0.01` (existing strategy default)
- `speed_scale = 0.03`
- `noise_lookback = 10`
- `noise_ratio_scale = 3.0`
- `score_weights = {depth: 0.45, speed: 0.25, stabilization: 0.20, noise_penalty: 0.10}`
- `use_shock_score_filter = False`
- `shock_score_min = 60`

## Rollout plan

### Phase 1 — design

Document formulas, defaults, and validation expectations.

### Phase 2 — passive instrumentation

Add per-signal score components to `signals.csv` and `shock_score_at_entry` to `trades.csv` while leaving entry behavior unchanged by default.

### Phase 3 — bucket analysis

Aggregate signal and trade quality by score buckets:

- `0–20`
- `20–40`
- `40–60`
- `60–80`
- `80–100`

Metrics per bucket:

- `signal_count`
- `executed_trades`
- `avg_pnl`
- `avg_mfe`
- `avg_mae`
- `avg_etd`
- `win_rate`
- `stop_loss_share`

### Phase 4 — optional filter

Enable score gating only when `use_shock_score_filter=True`, requiring:

```text
shock_score >= shock_score_min
```

### Phase 5 — conservative tuning

Keep code prepared for later tuning of:

- `speed_scale`
- `noise_lookback`
- `noise_ratio_scale`
- score weights
- `shock_score_min`

## Validation plan

The score is considered useful if higher-score buckets show, directionally:

- higher `avg_pnl`
- higher `win_rate`
- lower `stop_loss_share`
- better `avg_mfe` / `avg_mae` / `avg_etd` profile

Recommended validation flow:

1. Run the strategy with the filter disabled so behavior remains unchanged.
2. Inspect `signals.csv` to confirm all signal rows include the new score breakdown.
3. Inspect `trades.csv` to confirm executed trades carry `shock_score_at_entry`.
4. Review `shock_score_buckets.csv` to check monotonic improvement across score bands.
5. Only after passive analysis looks promising, test a conservative threshold such as `shock_score_min=60`.
