"""Result aggregation and ranking for experiment runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml


SUMMARY_COLUMNS = [
    "run_id",
    "sharpe",
    "total_return",
    "max_drawdown",
    "z_entry",
    "z_exit",
    "trade_count",
]

RANKING_DEFAULTS = {
    "sharpe": -999.0,
    "total_return": -999.0,
    "max_drawdown": 999.0,
}

# Structure placeholder for future expansion.
FUTURE_METRICS = ["profit_factor", "win_rate", "expectancy"]


def _safe_float(value: Any, fallback: float) -> float:
    """Return float value or fallback when value is missing/non-numeric."""
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON payload from file; return empty payload on failure."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML payload from file; return empty payload on failure."""
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def collect_run_results(output_root: Path) -> list[dict[str, Any]]:
    """Collect one record per run directory under an experiment output path."""
    records: list[dict[str, Any]] = []

    for run_dir in sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_")):
        metrics = _load_json(run_dir / "metrics.json")
        snapshot = _load_yaml(run_dir / "config_snapshot.yaml")
        parameters = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}

        record = {
            "run_id": run_dir.name,
            "sharpe": _safe_float(metrics.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            "total_return": _safe_float(metrics.get("total_return", metrics.get("rtot")), RANKING_DEFAULTS["total_return"]),
            "max_drawdown": _safe_float(metrics.get("max_drawdown"), RANKING_DEFAULTS["max_drawdown"]),
            "z_entry": parameters.get("z_entry"),
            "z_exit": parameters.get("z_exit"),
            "trade_count": metrics.get("num_trades", metrics.get("trade_count")),
        }
        records.append(record)

    return records


def _write_summary(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records to CSV with fixed column order."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column) for column in SUMMARY_COLUMNS})


def rank_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort records by sharpe desc, total return desc, max drawdown asc."""
    return sorted(
        records,
        key=lambda row: (
            -_safe_float(row.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            -_safe_float(row.get("total_return"), RANKING_DEFAULTS["total_return"]),
            _safe_float(row.get("max_drawdown"), RANKING_DEFAULTS["max_drawdown"]),
        ),
    )


def build_summary(experiment_name: str) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Build summary.csv + summary_sorted.csv for an experiment and return top-ranked records."""
    output_root = Path("outputs") / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)

    records = collect_run_results(output_root)
    summary_path = output_root / "summary.csv"
    _write_summary(summary_path, records)

    sorted_records = rank_results(records)
    summary_sorted_path = output_root / "summary_sorted.csv"
    _write_summary(summary_sorted_path, sorted_records)

    return summary_path, summary_sorted_path, sorted_records

