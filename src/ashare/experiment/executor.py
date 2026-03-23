"""Canonical experiment execution pipeline."""

from __future__ import annotations

import csv
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ashare.config.settings import BacktestConfig
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.analysis.experiment_dashboard import build_experiment_dashboard
from ashare.experiment.grid import expand_grid, generate_parameter_sets
from ashare.experiment.result import build_summary
from ashare.strategies.validation import validate_strategy_params
from ashare.utils.logging import get_logger

logger = get_logger("ashare.experiment.executor")

TRADE_EXPORT_COLUMNS = [
    "run_id",
    "symbol",
    "entry_datetime",
    "exit_datetime",
    "position_size",
    "entry_price",
    "avg_entry_price",
    "exit_price",
    "holding_period",
    "trade_return",
    "mfe",
    "mae",
    "etd",
    "mfe_price",
    "mae_price",
    "anchor_price_at_entry",
    "effective_anchor_price",
    "leg_count",
    "excursion_at_entry",
    "shock_score_at_entry",
    "add_shock_scores",
    "add_score_count",
    "add_score_min",
    "add_score_max",
    "add_score_avg",
    "recovery_target",
    "take_profit_price",
    "effective_target_price",
    "bars_to_mfe",
    "bars_to_mae",
    "exit_reason",
    "exit_subtype",
    "trade_pnl_amount",
]

SIGNAL_EXPORT_COLUMNS = [
    "run_id",
    "symbol",
    "datetime",
    "excursion",
    "depth_raw",
    "depth_score",
    "speed_ret",
    "speed_score",
    "stabilization_score",
    "noise_base",
    "noise_ratio",
    "noise_penalty",
    "entry_shock_score",
    "add_shock_score",
    "shock_score",
    "threshold",
    "entry_shock_score_min",
    "entry_shock_score_max",
    "shock_score_min",
    "shock_score_max",
    "add_score_min",
    "shock_score_filter_enabled",
    "blocked_by_shock_score_low",
    "blocked_by_shock_score_high",
    "trend_ok",
    "entry_executed",
    "add_executed",
    "execution_type",
]


def _read_pointer_target(pointer_file: Path) -> Path | None:
    """Read a pointer text file and resolve relative paths against its parent directory."""
    raw_target = pointer_file.read_text(encoding="utf-8").strip()
    if not raw_target:
        return None
    candidate = Path(raw_target)
    if not candidate.is_absolute():
        candidate = (pointer_file.parent / candidate).resolve()
    return candidate


def resolve_experiment_path(base_dir: Path, mode: str = "latest") -> Path | None:
    """Resolve the latest/previous experiment pointer via symlink or text fallback."""
    if mode not in {"latest", "previous"}:
        raise ValueError("mode must be 'latest' or 'previous'")

    pointer = base_dir / mode
    pointer_txt = base_dir / f"{mode}.txt"

    if pointer.is_symlink():
        return pointer.resolve()
    if pointer.exists():
        return pointer.resolve()
    if pointer_txt.exists():
        return _read_pointer_target(pointer_txt)
    return None


def _write_pointer_text(pointer_txt: Path, target_dir: Path) -> None:
    """Persist a directory pointer to a text file using a relative path when possible."""
    try:
        rendered = os.path.relpath(target_dir.resolve(), pointer_txt.parent.resolve())
    except ValueError:
        rendered = str(target_dir.resolve())
    pointer_txt.write_text(rendered, encoding="utf-8")


def update_experiment_pointers(base_dir: Path, new_run_dir: Path) -> Path | None:
    """Update latest/previous experiment run pointers with symlink and text fallbacks."""
    latest = base_dir / "latest"
    previous = base_dir / "previous"
    latest_txt = base_dir / "latest.txt"
    previous_txt = base_dir / "previous.txt"

    old_latest = resolve_experiment_path(base_dir, "latest")

    if old_latest and old_latest.exists():
        try:
            if previous.exists() or previous.is_symlink():
                previous.unlink()
            os.symlink(old_latest.resolve(), previous, target_is_directory=True)
            if previous_txt.exists():
                previous_txt.unlink()
        except OSError:
            _write_pointer_text(previous_txt, old_latest)
            if previous.exists() or previous.is_symlink():
                previous.unlink()
    else:
        if previous.exists() or previous.is_symlink():
            previous.unlink()
        if previous_txt.exists():
            previous_txt.unlink()

    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        os.symlink(new_run_dir.resolve(), latest, target_is_directory=True)
        if latest_txt.exists():
            latest_txt.unlink()
    except OSError:
        _write_pointer_text(latest_txt, new_run_dir)
        if latest.exists() or latest.is_symlink():
            latest.unlink()

    return old_latest


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Write rows to a stable CSV artifact."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})


def _report_grid_size(original_grid_size: int, deduplicated_runs: int) -> None:
    """Print grid-size diagnostics only when deduplication changes the run count."""
    if original_grid_size != deduplicated_runs:
        print(f"Original grid size: {original_grid_size}")
        print(f"Deduplicated runs: {deduplicated_runs}")




def resolve_output_root(
    *,
    experiment_name: str,
    output_name: str | None = None,
    use_timestamp: bool = True,
) -> tuple[str, Path]:
    """Resolve the per-run experiment output directory name and path."""
    base_name = str(output_name or experiment_name)
    run_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{base_name}" if use_timestamp else base_name
    return run_name, Path("outputs") / base_name / run_name


def prepare_output_dir(output_dir: str | Path, *, clean: bool = True) -> Path:
    """Create an experiment output directory and optionally clear existing contents."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    if not clean:
        return output_root

    for child in output_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return output_root


def execute_experiment_spec(
    *,
    strategy_cls,
    strategy_name: str,
    spec: dict[str, Any],
    config: BacktestConfig,
    clean_output: bool = True,
    use_timestamp: bool = True,
    update_pointers: bool = True,
) -> dict[str, Any]:
    """Execute an experiment spec and write canonical output artifacts."""
    execution = dict(spec.get("execution", {}))
    run_config = replace(
        config,
        initial_cash=float(execution.get("initial_cash", config.initial_cash)),
        commission=float(execution.get("commission", config.commission)),
    )
    parameters = validate_strategy_params(strategy_name, dict(spec.get("parameters", {})))
    grid = dict(spec.get("grid", {}))
    for key, values in grid.items():
        for value in values:
            validate_strategy_params(strategy_name, {key: value})
    all_combinations = [dict(parameters, **combo) for combo in expand_grid(grid)]
    final_runs = generate_parameter_sets({"strategy": strategy_name, "parameters": parameters, "grid": grid})

    _report_grid_size(len(all_combinations), len(final_runs))

    experiment_name = spec["name"]
    base_output_name = str(spec.get("output_name") or experiment_name)
    output_name, output_root = resolve_output_root(
        experiment_name=experiment_name,
        output_name=base_output_name,
        use_timestamp=use_timestamp,
    )
    base_dir = output_root.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    output_root = prepare_output_dir(output_root, clean=clean_output)
    print(f"Experiment run directory: {output_root.resolve()}")

    previous_run = None
    if update_pointers:
        previous_run = update_experiment_pointers(base_dir, output_root)
        print(f"Latest pointer → {output_root.resolve()}")
        print(f"Previous pointer → {previous_run.resolve() if previous_run else 'None'}")

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
            for key in ordered_keys:
                if key not in params:
                    raise ValueError(f"Missing parameter: {key}")
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
                config=run_config,
                strategy_params=params,
                symbol=symbol,
                experiment_name=experiment_name,
                run_id=f"run_{run_index:03d}",
                output_dir=run_dir,
            )
            (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

            trade_rows = getattr(strat, "completed_trades", None)
            if trade_rows:
                experiment_trades.extend(
                    {
                        "run_id": f"run_{run_index:03d}",
                        **trade_row,
                    }
                    for trade_row in trade_rows
                )

            signal_rows = getattr(strat, "signal_events", None)
            if signal_rows:
                experiment_signals.extend(
                    {
                        "run_id": f"run_{run_index:03d}",
                        **signal_row,
                    }
                    for signal_row in signal_rows
                )

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
                "initial_cash": run_config.initial_cash,
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
                    "initial_cash": run_config.initial_cash,
                },
            }
            (run_dir / "run_result.json").write_text(json.dumps(run_payload, indent=2), encoding="utf-8")

    trades_path = output_root / "trades.csv"
    signals_path = output_root / "signals.csv"
    _write_csv(trades_path, experiment_trades, TRADE_EXPORT_COLUMNS)
    _write_csv(signals_path, experiment_signals, SIGNAL_EXPORT_COLUMNS)

    summary_path, summary_sorted_path, ranked_records = build_summary(output_root)
    dashboard_outputs = build_experiment_dashboard(str(output_root))
    run_performance_report_path = output_root / "run_performance_report.csv"
    return {
        "experiment_name": experiment_name,
        "output_name": output_name,
        "output_dir": str(output_root),
        "summary_path": str(summary_path),
        "summary_sorted_path": str(summary_sorted_path),
        "run_performance_report_path": str(run_performance_report_path),
        "trades_path": str(trades_path),
        "signals_path": str(signals_path),
        "dashboard_dir": str(output_root / "dashboard"),
        "dashboard_outputs": dashboard_outputs,
        "num_runs": total_runs,
        "results": ranked_records,
    }
