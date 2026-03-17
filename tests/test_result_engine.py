import json
from pathlib import Path

import yaml

from ashare.experiment.result import build_summary, collect_run_results, rank_results


def _write_run(
    output_root: Path,
    run_id: str,
    metrics: dict | None,
    parameters: dict | None = None,
) -> None:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if metrics is not None:
        (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    snapshot = {"parameters": parameters or {}}
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(snapshot, sort_keys=False), encoding="utf-8")


def test_collect_and_build_summary_outputs_csv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "demo_experiment"
    output_root.mkdir(parents=True, exist_ok=True)

    _write_run(
        output_root,
        "run_001",
        metrics={"sharpe": 1.2, "total_return": 0.18, "max_drawdown": 0.12, "num_trades": 8},
        parameters={"z_entry": [-1.5, -2.0], "z_exit": [1.0]},
    )
    _write_run(
        output_root,
        "run_002",
        metrics={"sharpe": 1.8, "total_return": 0.25, "max_drawdown": 0.10, "num_trades": 10},
        parameters={"z_entry": [-2.0, -2.5], "z_exit": [1.2]},
    )

    summary_path, sorted_path, ranked = build_summary("demo_experiment")

    assert summary_path.exists()
    assert sorted_path.exists()
    assert ranked[0]["run_id"] == "run_002"
    assert ranked[1]["run_id"] == "run_001"

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "run_id,sharpe,total_return,max_drawdown,z_entry,z_exit,trade_count" in summary_text


def test_rank_results_handles_missing_metrics() -> None:
    records = [
        {"run_id": "run_001", "sharpe": None, "total_return": 0.2, "max_drawdown": 0.1},
        {"run_id": "run_002", "sharpe": 1.1, "total_return": 0.1, "max_drawdown": 0.2},
        {"run_id": "run_003", "total_return": None, "max_drawdown": None},
    ]

    ranked = rank_results(records)

    assert ranked[0]["run_id"] == "run_002"
    assert ranked[-1]["run_id"] == "run_003"


def test_collect_run_results_tolerates_missing_files(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs" / "missing_metrics"
    output_root.mkdir(parents=True, exist_ok=True)

    _write_run(output_root, "run_001", metrics=None, parameters={"z_entry": [-2.0], "z_exit": [1.2]})

    records = collect_run_results(output_root)

    assert len(records) == 1
    assert records[0]["run_id"] == "run_001"
    assert records[0]["sharpe"] == -999.0
