"""Experiment runner for systematic strategy research."""

from __future__ import annotations

import json
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest


RESULT_COLUMNS = [
    "symbol",
    "total_return",
    "sharpe",
    "max_drawdown",
]


def generate_param_combinations(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Expand param grid into list of parameter dictionaries."""
    if not param_grid:
        return [{}]

    keys = list(param_grid.keys())
    values = [param_grid[key] for key in keys]
    combinations = []

    for combo in product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations


def run_experiment(
    strategy_cls,
    symbols: list[str],
    param_grid: dict[str, list[Any]],
    start_date: str,
    end_date: str,
    config: BacktestConfig,
) -> dict[str, Any]:
    """Run a parameter-sweep experiment across symbols and save results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_dir = Path("experiments") / f"experiment_{timestamp}"
    experiment_dir.mkdir(parents=True, exist_ok=False)

    combinations = generate_param_combinations(param_grid)

    records: list[dict[str, Any]] = []
    for symbol in symbols:
        data_df = load_minute_30(ts_code=symbol, start_date=start_date, end_date=end_date)

        for params in combinations:
            _, _, metrics = run_backtest(
                strategy_cls=strategy_cls,
                data_df=data_df,
                config=config,
                strategy_params=params,
                symbol=symbol,
            )

            row = {
                "symbol": symbol,
                **params,
                "total_return": metrics.get("total_return", metrics.get("rtot")),
                "sharpe": metrics.get("sharpe"),
                "max_drawdown": metrics.get("max_drawdown"),
            }
            records.append(row)

    results_df = pd.DataFrame(records)
    if not results_df.empty:
        param_cols = list(param_grid.keys())
        ordered_cols = ["symbol", *param_cols, "total_return", "sharpe", "max_drawdown"]
        results_df = results_df[ordered_cols]

    results_path = experiment_dir / "results.csv"
    results_df.to_csv(results_path, index=False)

    config_payload = {
        "strategy": strategy_cls.__name__,
        "symbols": symbols,
        "param_grid": param_grid,
        "start_date": start_date,
        "end_date": end_date,
        "backtest_config": {
            "initial_cash": config.initial_cash,
            "commission": config.commission,
            "stamp_duty": config.stamp_duty,
            "slippage_perc": config.slippage_perc,
        },
        "combinations": len(combinations),
        "runs": len(records),
    }
    config_path = experiment_dir / "config.json"
    config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    return {
        "experiment_dir": str(experiment_dir),
        "config_path": str(config_path),
        "results_path": str(results_path),
        "num_runs": len(records),
        "num_combinations": len(combinations),
    }
