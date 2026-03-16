"""Walk-forward optimization for robust strategy validation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.research.experiment_runner import generate_param_combinations


def _normalize_window_size(window: int | timedelta) -> timedelta:
    """Normalize integer day windows to ``timedelta`` values."""
    if isinstance(window, timedelta):
        return window
    if isinstance(window, int) and window > 0:
        return timedelta(days=window)
    raise ValueError("Window size must be a positive integer (days) or timedelta")


def generate_walk_forward_windows(
    start_date: str,
    end_date: str,
    train_window: int | timedelta,
    test_window: int | timedelta,
) -> list[dict[str, str]]:
    """Generate rolling train/test windows for walk-forward optimization."""
    train_delta = _normalize_window_size(train_window)
    test_delta = _normalize_window_size(test_window)

    current_start = datetime.fromisoformat(start_date)
    final_end = datetime.fromisoformat(end_date)

    windows: list[dict[str, str]] = []
    while True:
        train_end = current_start + train_delta
        test_end = train_end + test_delta
        if test_end > final_end:
            break

        windows.append(
            {
                "train_start": current_start.date().isoformat(),
                "train_end": train_end.date().isoformat(),
                "test_start": train_end.date().isoformat(),
                "test_end": test_end.date().isoformat(),
            }
        )
        current_start = current_start + test_delta

    return windows


def _select_best_params(
    strategy_cls,
    train_df: pd.DataFrame,
    param_grid: dict[str, list[Any]],
    config: BacktestConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run in-sample optimization and return best params and metrics."""
    best_params: dict[str, Any] = {}
    best_metrics: dict[str, Any] = {}
    best_score = float("-inf")

    for params in generate_param_combinations(param_grid):
        _, _, metrics = run_backtest(
            strategy_cls=strategy_cls,
            data_df=train_df,
            config=config,
            strategy_params=params,
        )

        sharpe = metrics.get("sharpe")
        score = sharpe if sharpe is not None else metrics.get("total_return", metrics.get("rtot", float("-inf")))

        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics

    return best_params, best_metrics


def run_walk_forward(
    strategy_cls,
    symbol: str,
    param_grid: dict[str, list[Any]],
    start_date: str,
    end_date: str,
    train_window: int | timedelta,
    test_window: int | timedelta,
    config: BacktestConfig,
) -> dict[str, Any]:
    """Execute rolling walk-forward optimization and persist OOS outputs."""
    windows = generate_walk_forward_windows(start_date, end_date, train_window, test_window)
    if not windows:
        raise ValueError("No walk-forward windows generated. Check date range and window sizes.")

    full_df = load_minute_30(ts_code=symbol, start_date=start_date, end_date=end_date)

    results: list[dict[str, Any]] = []
    for window in windows:
        train_df = full_df.loc[window["train_start"]:window["train_end"]]
        test_df = full_df.loc[window["test_start"]:window["test_end"]]

        if train_df.empty or test_df.empty:
            continue

        best_params, _ = _select_best_params(
            strategy_cls=strategy_cls,
            train_df=train_df,
            param_grid=param_grid,
            config=config,
        )

        _, _, test_metrics = run_backtest(
            strategy_cls=strategy_cls,
            data_df=test_df,
            config=config,
            strategy_params=best_params,
            symbol=symbol,
        )

        results.append(
            {
                "symbol": symbol,
                "train_start": window["train_start"],
                "train_end": window["train_end"],
                "test_start": window["test_start"],
                "test_end": window["test_end"],
                "best_parameters": json.dumps(best_params, ensure_ascii=False),
                "test_return": test_metrics.get("total_return", test_metrics.get("rtot")),
                "test_sharpe": test_metrics.get("sharpe"),
                "test_drawdown": test_metrics.get("max_drawdown"),
            }
        )

    if not results:
        raise ValueError("No valid walk-forward windows with data were produced.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("experiments") / f"walk_forward_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)

    results_df = pd.DataFrame(results)
    results_path = output_dir / "results.csv"
    results_df.to_csv(results_path, index=False)

    sharpe_series = pd.to_numeric(results_df["test_sharpe"], errors="coerce").fillna(0.0)
    drawdown_series = pd.to_numeric(results_df["test_drawdown"], errors="coerce").fillna(0.0)
    return_series = pd.to_numeric(results_df["test_return"], errors="coerce").fillna(0.0)

    summary = {
        "total_return": float(return_series.sum()),
        "average_sharpe": float(sharpe_series.mean()),
        "max_drawdown": float(drawdown_series.max()),
        "num_windows": int(len(results_df)),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    windows_path = output_dir / "windows.json"
    windows_path.write_text(json.dumps(windows, indent=2), encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "results_path": str(results_path),
        "summary_path": str(summary_path),
        "windows_path": str(windows_path),
        "num_windows": len(results_df),
        "summary": summary,
    }
