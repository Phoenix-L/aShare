# shock_reversion_intraday — User Manual

**Version:** v0.6.0

## Run a CLI Experiment

Example using a YAML experiment file:

```bash
ashare experiment configs/experiments/shock_reversion_intraday_template.yaml
```

Example using direct CLI parameters:

```bash
ashare experiment \
  --strategy shock_reversion_intraday \
  --symbols 002850.SZ \
  --start 2025-07-01 \
  --end 2026-02-28 \
  --param excursion_lookback_bars=8,12,16 \
  --param excursion_threshold=0.03,0.05 \
  --param recovery_frac=0.5 \
  --param take_profit_pct=0.03,0.05 \
  --param stop_loss_pct=0.03 \
  --param max_hold_bars=40 \
  --param use_shock_score_filter=true \
  --param shock_score_min=30 \
  --param shock_score_max=80
```

## Parameter Guide

- `excursion_lookback_bars`: number of intraday bars used to form the rolling close anchor
- `excursion_threshold`: minimum downside excursion required to arm an entry
- `recovery_frac`: fraction of the shock depth that must be recovered for a recovery exit
- `take_profit_pct`: fixed profit target measured from entry price
- `stop_loss_pct`: fixed stop measured from entry price
- `max_hold_bars`: maximum number of bars a position can stay open
- `use_shock_score_filter`: enables score-based gating on otherwise valid excursion signals
- `shock_score_min`: lower score bound when the score filter is active
- `shock_score_max`: optional upper score bound used to reject overshocked signals

## Output Files

- `trades.csv`: one row per completed trade with normalized trade metrics such as `trade_return`, `mfe`, `mae`, and `etd`
- `diagnostics_summary.json`: run-level signal counts, block reasons, and average trade-quality metrics
- `run_performance_report.csv`: canonical run-level metrics across symbols and parameter sets
- `selection_report_v2.csv`: ranked shortlist for the next research phase using the stabilized scoring model

## Interpretation Guide

### `sum_trade_return` vs `compound_trade_return` vs `total_return_simple`

- `sum_trade_return` is the arithmetic sum of per-trade returns.
- `compound_trade_return` compounds those trade returns as if capital were fully recycled from trade to trade.
- `total_return_simple` is the realized portfolio equity return and therefore includes cash drag, fixed sizing, and financing effects.

In this strategy, `sum_trade_return` or `compound_trade_return` can be materially higher than `total_return_simple` when the trade logic works but capital is underutilized.

### `capital_efficiency`

`capital_efficiency = total_return_simple / sum_trade_return`

A higher value means more of the raw trade-return opportunity is translating into actual portfolio equity growth. A lower value usually means idle cash, fixed trade sizing, or financing friction are reducing realized portfolio efficiency.

## Practical Notes

- CLI output may display percentages for readability, but stored report values remain decimal ratios.
- `selection_report_v2.csv` is expected to be non-empty for a healthy experiment universe with enough viable runs.
- This release is pre-ladder: use the ranking output to choose stable single-entry baselines before introducing multi-leg entries.
