"""Deprecated experiment runner wrappers for systematic strategy research."""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

from ashare.config.settings import BacktestConfig
from ashare.experiment.executor import execute_experiment_spec
from ashare.experiment.grid import generate_parameter_sets

def generate_param_combinations(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Backward-compatible wrapper for parameter grid expansion."""
    return generate_parameter_sets({"parameters": {}, "grid": param_grid})



def run_experiment(
    strategy_cls,
    symbols: list[str],
    param_grid: dict[str, list[Any]],
    start_date: str,
    end_date: str,
    config: BacktestConfig,
    base_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run experiment via canonical YAML-compatible pipeline (deprecated API)."""
    warnings.warn(
        "run_experiment() is deprecated; use the CLI YAML pipeline or execute_experiment_spec().",
        DeprecationWarning,
        stacklevel=2,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    spec = {
        "name": f"experiment_{timestamp}",
        "strategy": strategy_cls.__name__,
        "symbols": symbols,
        "start": start_date,
        "end": end_date,
        "parameters": dict(base_params or {}),
        "grid": dict(param_grid),
    }

    result = execute_experiment_spec(
        strategy_cls=strategy_cls,
        strategy_name=strategy_cls.__name__,
        spec=spec,
        config=config,
    )

    notice_path = Path(result["output_dir"]) / "deprecated_api_notice.txt"
    notice_path.write_text(
        "Deprecated API: run_experiment() now delegates to canonical CLI-compatible pipeline.\n",
        encoding="utf-8",
    )

    return {
        "experiment_dir": result["output_dir"],
        "config_path": str(notice_path),
        "results_path": result["summary_path"],
        "num_runs": result["num_runs"],
        "num_combinations": len(generate_param_combinations(param_grid)),
        "results": [{"params": {}, "metrics": r} for r in result["results"]],
    }
