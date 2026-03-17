# Core–Satellite Mean Reversion Strategy: CLI User Manual

## 1) Overview
The `core_satellite` strategy is designed for individual quant researchers who want to keep a persistent **core long exposure** while running tactical **mean-reversion satellite trades** around that core.

You run it through the `ashare` CLI using:
- `ashare backtest` for a single-symbol single-run validation
- `ashare experiment` for multi-run parameter sweeps

The strategy name in CLI is:

```bash
--strategy core_satellite
```

---

## 2) Strategy Concept

### Core sleeve
- Maintains a baseline long position (`core_position` shares).
- Exit logic is constrained so the strategy should not sell below core size.

### Satellite sleeve
- Adds/removes tactical position based on Z-score mean-reversion signals.
- Satellite size is capped by `satellite_max`.
- Orders are executed in `trade_unit` blocks.

### Ladder entry system (current behavior)
- Entry checks each threshold in `z_entry` (for example `-1.5`, `-2.0`, `-2.5`).
- If Z-score is below a threshold, strategy can add one `trade_unit` (subject to caps and filters).

### Z-score signal
The strategy computes:

\[
Z = \frac{Close - SMA(20)}{ATR(14)}
\]

Then:
- lower Z-score zones trigger satellite **entries** (`z_entry`)
- higher Z-score zones trigger satellite **exits** (`z_exit`)

### Trend filter
When enabled (`trend_filter=true`), new satellite buys are blocked when:

```text
price < MA120
```

---

## 3) Strategy Parameters

The current strategy-exposed parameters are:

- `core_position` (int)
  - Target baseline core holding (shares).
- `satellite_max` (int)
  - Maximum tactical sleeve size (shares).
- `trade_unit` (int)
  - Single order size for satellite entries/exits (shares).
- `z_entry` (list[float])
  - Entry thresholds for ladder-style buy logic.
- `z_exit` (list[float])
  - Exit thresholds for ladder-style sell logic.
- `z_entry_mode` (str, placeholder)
  - Reserved for future entry-mode extension. Current expected default: `ladder`.
  - **Important:** currently does not alter behavior.
- `trend_filter` (bool)
  - Enables/disables MA120 filter for new satellite buys.

Default configuration file:

```text
configs/core_satellite.yaml
```

---

## 4) CLI Usage

## 4.1 Run a simple backtest

```bash
ashare backtest \
  --strategy core_satellite \
  --symbol 002850.SZ \
  --start 2024-01-01 \
  --end 2025-01-01
```

Optional plotting:

```bash
ashare backtest \
  --strategy core_satellite \
  --symbol 002850.SZ \
  --start 2024-01-01 \
  --end 2025-01-01 \
  --plot
```

## 4.2 Run an experiment with parameter overrides

```bash
ashare experiment \
  --strategy core_satellite \
  --symbols 002850.SZ \
  --param z_entry=-1.5,-2.0,-2.5 \
  --param z_exit=0.8,1.2,1.5 \
  --param trend_filter=true \
  --start 2024-01-01 \
  --end 2025-01-01
```

### Passing list parameters (`z_entry`, `z_exit`)
For list-typed strategy params, the CLI parser accepts comma-separated values and passes them as a single list override (rather than scalar Cartesian expansion).

### Placeholder parameter override (`z_entry_mode`)
Accepted by CLI for forward compatibility:

```bash
ashare experiment \
  --strategy core_satellite \
  --symbols 002850.SZ \
  --param z_entry_mode=ladder \
  --start 2024-01-01 \
  --end 2025-01-01
```

---

## 5) Strategy Behavior (Current Phase)

### Entry ladder behavior
- On each bar, compute Z-score.
- Iterate through `z_entry` thresholds.
- If `zscore <= threshold`, attempt buy of `trade_unit`.
- Enforce `satellite_max` cap.
- If `trend_filter=true` and `close < MA120`, skip new satellite buys.

### Exit behavior
- Iterate through `z_exit` thresholds.
- If `zscore >= threshold`, attempt sell of `trade_unit`.
- Never reduce total position below `core_position`.

### Position limits
- Core sleeve intended as persistent base exposure.
- Satellite sleeve bounded to `[0, satellite_max]` by trade sizing and checks.

---

## 6) Example Research Workflow

1. **Start with baseline backtest**
   - Run `ashare backtest` for one symbol/date range.
   - Confirm data availability and baseline metrics.

2. **Run parameter experiments**
   - Use `ashare experiment` with `--param` to vary thresholds and sizing.
   - Keep lists for `z_entry`/`z_exit` as planned signal ladders.

3. **Review outputs**
   - CLI prints experiment output directory and CSV path.
   - Compare total return, Sharpe, and max drawdown across runs.

4. **Tune and repeat**
   - Adjust `trade_unit`, `satellite_max`, and threshold ladders.
   - Re-run experiments with narrower ranges around promising settings.

5. **Operationalize candidate settings**
   - Persist chosen defaults in `configs/core_satellite.yaml`.
   - Keep CLI overrides for rapid ad-hoc scenario testing.

---

## 7) Future Extensions
Potential roadmap directions:

- **Volatility regime switching**
  - adapt behavior by market regime state.
- **Adaptive entry thresholds**
  - dynamic threshold generation from recent volatility/dispersion.
- **Portfolio multi-symbol support**
  - coordinated allocation/risk constraints across symbols.

`z_entry_mode` exists to help evolve entry mechanisms while preserving backward-compatible CLI/config interfaces.
