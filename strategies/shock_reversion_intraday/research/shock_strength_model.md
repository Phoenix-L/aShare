# shock_reversion_intraday — Shock Strength Model v1

## Objective

Design an interpretable, strategy-local score that ranks downside shock events for `shock_reversion_intraday`.

The score favors deeper, faster downside shocks with early stabilization and penalizes moves that are small relative to recent bar-to-bar noise.

## Scope

- Applies only to `shock_reversion_intraday`.
- Uses only the current intraday feed.
- No machine learning.
- Score is a signal-quality model; trade management (including ladder adds/exits) is handled separately by strategy/execution logic.

## Locked v1 feature definitions

### 1. Depth score

```text
excursion = (close - rolling_max(close, N)) / rolling_max(close, N)
depth_raw = abs(excursion)
depth_score = clip(depth_raw / (2 * excursion_threshold), 0, 1)
```

### 2. Speed score

```text
speed_ret = (close[0] - close[-2]) / close[-2]
speed_scale = 0.03
speed_score = clip(abs(min(speed_ret, 0)) / speed_scale, 0, 1)
```

### 3. Stabilization score

Start at `0.0`.

Add `0.5` if `close[0] > close[-1]`.

Define:

```text
close_location = (close - low) / (high - low + eps)
```

Add `0.5` if `close_location >= 0.5`.

Final score is one of `{0.0, 0.5, 1.0}`.

### 4. Noise penalty

```text
noise_lookback = 10
noise_base = mean(abs(ret_1bar), over last 10 bars)
noise_ratio = depth_raw / (noise_base + eps)
noise_ratio_scale = 3.0
noise_penalty = 1 - clip(noise_ratio / noise_ratio_scale, 0, 1)
```

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

## Weight sets in current implementation

The same component stack is used with separate weight sets:

- `entry_score_weight_*` for `entry_shock_score`
- `add_score_weight_*` for `add_shock_score`
- fallback defaults remain `{depth: 0.45, speed: 0.25, stabilization: 0.20, noise_penalty: 0.10}`

## Interpretation bands (research heuristic)

- `< 40`: weak
- `40–60`: moderate
- `60–80`: strong
- `> 80`: exceptional
