"""Canonical experiment execution pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ashare.config.settings import BacktestConfig
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.experiment.grid import generate_parameter_sets
from ashare.experiment.result import build_summary
from ashare.utils.logging import get_logger

logger = get_logger("ashare.experiment.executor")


def execute_experiment_spec(
    *,
    strategy_cls,
    strategy_name: str,
    spec: dict[str, Any],
    config: BacktestConfig,
) -> dict[str, Any]:
    """Execute an experiment spec and write canonical output artifacts."""
    parameters = dict(spec.get("parameters", {}))
    grid = dict(spec.get("grid", {}))
    combinations = generate_parameter_sets({"parameters": parameters, "grid": grid})

    experiment_name = spec["name"]
    output_root = Path("outputs") / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)

    symbol_data = {
        symbol: load_minute_30(ts_code=symbol, start_date=spec["start"], end_date=spec["end"])
        for symbol in spec["symbols"]
    }

    total_runs = len(combinations) * len(spec["symbols"])
    run_index = 0
    for symbol in spec["symbols"]:
        data_df = symbol_data[symbol]
        if data_df.empty:
            raise ValueError(f"No data returned for {symbol}. Check symbol and date range.")

        for params in combinations:
            run_index += 1
            ordered_keys = [*grid.keys(), *[key for key in params if key not in grid]]
            rendered_params = ", ".join(
                f"{key}={str(params[key]).lower() if isinstance(params[key], bool) else params[key]}"
                for key in ordered_keys
            )
            logger.info(f"Running: {rendered_params}")
            run_dir = output_root / f"run_{run_index:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)

            _, _, metrics = run_backtest(
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

    summary_path, summary_sorted_path, ranked_records = build_summary(experiment_name)
    return {
        "experiment_name": experiment_name,
        "output_dir": str(output_root),
        "summary_path": str(summary_path),
        "summary_sorted_path": str(summary_sorted_path),
        "num_runs": total_runs,
        "results": ranked_records,
    }

