"""Canonical experiment execution pipeline."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from ashare.config.settings import BacktestConfig
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.experiment.grid import expand_grid, generate_parameter_sets
from ashare.experiment.result import build_summary
from ashare.strategies.validation import validate_strategy_params
from ashare.utils.logging import get_logger

logger = get_logger("ashare.experiment.executor")

TRADE_EXPORT_COLUMNS = [
    "symbol",
    "entry_datetime",
    "exit_datetime",
    "entry_price",
    "exit_price",
    "holding_bars",
    "pnl_pct",
    "mfe_pct",
    "mae_pct",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "anchor_price_at_entry",
    "excursion_at_entry",
    "recovery_target",
    "take_profit_price",
    "effective_target_price",
    "bars_to_mfe",
    "bars_to_mae",
    "exit_reason",
    "exit_subtype",
]

SIGNAL_EXPORT_COLUMNS = [
    "symbol",
    "datetime",
    "excursion",
    "threshold",
    "trend_ok",
    "entry_executed",
]


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Write rows to a stable CSV artifact."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})


def execute_experiment_spec(
    *,
    strategy_cls,
    strategy_name: str,
    spec: dict[str, Any],
    config: BacktestConfig,
) -> dict[str, Any]:
    """Execute an experiment spec and write canonical output artifacts."""
    parameters = validate_strategy_params(strategy_name, dict(spec.get("parameters", {})))
    grid = dict(spec.get("grid", {}))
    for key, values in grid.items():
        for value in values:
            validate_strategy_params(strategy_name, {key: value})
    all_combinations = [dict(parameters, **combo) for combo in expand_grid(grid)]
    final_runs = generate_parameter_sets({"strategy": strategy_name, "parameters": parameters, "grid": grid})

    print(f"Original grid size: {len(all_combinations)}")
    print(f"Deduplicated runs: {len(final_runs)}")

    experiment_name = spec["name"]
    output_root = Path("outputs") / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)

    symbol_data = {
        symbol: load_minute_30(ts_code=symbol, start_date=spec["start"], end_date=spec["end"])
        for symbol in spec["symbols"]
    }
    experiment_trades: list[dict[str, Any]] = []
    experiment_signals: list[dict[str, Any]] = []

    total_runs = len(final_runs) * len(spec["symbols"])
    run_index = 0
    for symbol in spec["symbols"]:
        data_df = symbol_data[symbol]
        if data_df.empty:
            raise ValueError(f"No data returned for {symbol}. Check symbol and date range.")

        for params in final_runs:
            run_index += 1
            ordered_keys = [*grid.keys(), *[key for key in params if key not in grid]]
            rendered_params = ", ".join(
                f"{key}={str(params[key]).lower() if isinstance(params[key], bool) else params[key]}"
                for key in ordered_keys
            )
            logger.info(f"Running: {rendered_params}")
            run_dir = output_root / f"run_{run_index:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)

            _, strat, metrics = run_backtest(
                strategy_cls=strategy_cls,
                data_df=data_df,
                config=config,
                strategy_params=params,
                symbol=symbol,
                experiment_name=experiment_name,
                run_id=f"run_{run_index:03d}",
                output_dir=run_dir,
            )
            (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

            trade_rows = getattr(strat, "completed_trades", None)
            if trade_rows:
                experiment_trades.extend(trade_rows)

            signal_rows = getattr(strat, "signal_events", None)
            if signal_rows:
                experiment_signals.extend(signal_rows)

            diagnostics_path = run_dir / "diagnostics.json"
            diagnostics_summary_path = run_dir / "diagnostics_summary.json"
            if "diagnostics_summary" in metrics:
                if not diagnostics_path.exists() or not diagnostics_summary_path.exists():
                    raise FileNotFoundError(
                        f"Missing diagnostics artifacts for run_{run_index:03d}: "
                        f"{diagnostics_path} / {diagnostics_summary_path}"
                    )
                logger.info("Diagnostics saved to:\n%s", diagnostics_summary_path.resolve())

            snapshot = {
                "strategy": strategy_name,
                "parameters": params,
                "symbol": symbol,
                "date_range": {"start": spec["start"], "end": spec["end"]},
            }
            (run_dir / "config_snapshot.yaml").write_text(
                yaml.safe_dump(snapshot, sort_keys=False),
                encoding="utf-8",
            )
            run_payload = {
                "params": params,
                "metrics": metrics,
                "meta": {
                    "run_id": f"run_{run_index:03d}",
                    "strategy": strategy_name,
                    "symbol": symbol,
                    "experiment_name": experiment_name,
                    "date_range": {"start": spec["start"], "end": spec["end"]},
                },
            }
            (run_dir / "run_result.json").write_text(json.dumps(run_payload, indent=2), encoding="utf-8")

    trades_path = output_root / "trades.csv"
    signals_path = output_root / "signals.csv"
    _write_csv(trades_path, experiment_trades, TRADE_EXPORT_COLUMNS)
    _write_csv(signals_path, experiment_signals, SIGNAL_EXPORT_COLUMNS)

    summary_path, summary_sorted_path, ranked_records = build_summary(experiment_name)
    return {
        "experiment_name": experiment_name,
        "output_dir": str(output_root),
        "summary_path": str(summary_path),
        "summary_sorted_path": str(summary_sorted_path),
        "trades_path": str(trades_path),
        "signals_path": str(signals_path),
        "num_runs": total_runs,
        "results": ranked_records,
    }
