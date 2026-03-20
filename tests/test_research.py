from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ashare.cli import cli
from ashare.research import analyze_experiment, generate_markdown_report


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_snapshot(path, parameters) -> None:
    path.write_text(
        "strategy: mean_reversion_advanced\n"
        f"parameters:\n"
        + "".join(f"  {key}: {str(value).lower() if isinstance(value, bool) else value}\n" for key, value in parameters.items()),
        encoding="utf-8",
    )


def _build_mock_experiment(output_dir) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.csv").write_text(
        "z_entry,z_exit,use_atr_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe,max_drawdown,num_trades\n"
        "-1.1,0.3,True,False,2,0.008,0.05,1.0,4.0,3\n"
        "-1.2,0.3,True,False,3,0.010,0.07,1.2,4.2,4\n"
        "-1.4,0.5,True,True,3,0.010,0.12,1.8,3.8,6\n"
        "-1.6,0.5,True,True,5,0.015,0.10,1.6,4.1,5\n",
        encoding="utf-8",
    )
    (output_dir / "summary_sorted.csv").write_text(
        "z_entry,z_exit,use_atr_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe,max_drawdown,num_trades\n"
        "-1.4,0.5,True,True,3,0.010,0.12,1.8,3.8,6\n"
        "-1.6,0.5,True,True,5,0.015,0.10,1.6,4.1,5\n"
        "-1.2,0.3,True,False,3,0.010,0.07,1.2,4.2,4\n"
        "-1.1,0.3,True,False,2,0.008,0.05,1.0,4.0,3\n",
        encoding="utf-8",
    )

    runs = [
        (
            "run_001",
            {"z_entry": -1.1, "z_exit": 0.3, "use_multi_day_excursion": False, "excursion_window": 2, "excursion_min": 0.008},
            {"total_return": 0.05, "sharpe": 1.0},
            {"entry_signals": 10, "executed_trades": 2, "blocked_by_atr": 6},
        ),
        (
            "run_002",
            {"z_entry": -1.2, "z_exit": 0.3, "use_multi_day_excursion": False, "excursion_window": 3, "excursion_min": 0.010},
            {"total_return": 0.07, "sharpe": 1.2},
            {"entry_signals": 8, "executed_trades": 2, "blocked_by_atr": 4},
        ),
        (
            "run_003",
            {"z_entry": -1.4, "z_exit": 0.5, "use_multi_day_excursion": True, "excursion_window": 3, "excursion_min": 0.010},
            {"total_return": 0.12, "sharpe": 1.8},
            {"entry_signals": 6, "executed_trades": 2, "blocked_by_atr": 3},
        ),
        (
            "run_004",
            {"z_entry": -1.6, "z_exit": 0.5, "use_multi_day_excursion": True, "excursion_window": 5, "excursion_min": 0.015},
            {"total_return": 0.10, "sharpe": 1.6},
            {"entry_signals": 4, "executed_trades": 1, "blocked_by_atr": 2},
        ),
    ]

    for run_name, parameters, metrics, diagnostics in runs:
        run_dir = output_dir / run_name
        run_dir.mkdir()
        _write_json(run_dir / "metrics.json", metrics)
        _write_json(run_dir / "diagnostics_summary.json", diagnostics)
        _write_snapshot(run_dir / "config_snapshot.yaml", parameters)


def test_analyze_experiment_aggregates_metrics_and_grouping_correctly(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "demo"
    _build_mock_experiment(output_dir)

    results = analyze_experiment(str(output_dir))

    assert results["total_runs"] == 4
    assert results["best_sharpe"] == 1.8
    assert results["best_return"] == 0.12
    assert results["avg_sharpe"] == 1.4
    assert results["avg_return"] == pytest.approx(0.085)
    assert results["trade_efficiency"]["avg"] == pytest.approx(0.2583333333333333)
    assert results["filters"]["blocked_by_atr"] == pytest.approx(0.525)
    assert results["top_configs"][0]["rank"] == 1
    assert results["top_configs"][0]["params"]["use_multi_day_excursion"] is True

    excursion_toggle = results["parameter_analysis"]["excursion_toggle"]
    assert excursion_toggle[True]["avg_sharpe"] == pytest.approx(1.7)
    assert excursion_toggle[True]["avg_return"] == pytest.approx(0.11)
    assert excursion_toggle[True]["num_runs"] == 2
    assert excursion_toggle[False]["avg_sharpe"] == pytest.approx(1.1)
    assert excursion_toggle[False]["avg_return"] == pytest.approx(0.06)
    assert excursion_toggle[False]["num_runs"] == 2

    excursion_min = results["parameter_analysis"]["excursion_min"]
    assert excursion_min[0.01]["avg_sharpe"] == pytest.approx(1.5)
    assert excursion_min[0.01]["avg_return"] == pytest.approx(0.095)
    assert excursion_min[0.01]["num_runs"] == 2

    excursion_window = results["parameter_analysis"]["excursion_window"]
    assert excursion_window[3.0]["avg_sharpe"] == pytest.approx(1.5)
    assert excursion_window[3.0]["avg_return"] == pytest.approx(0.095)
    assert excursion_window[3.0]["num_runs"] == 2


def test_generate_markdown_report_contains_parameter_sections_and_insights() -> None:
    report = generate_markdown_report(
        {
            "total_runs": 4,
            "best_sharpe": 1.8,
            "best_return": 0.12,
            "avg_sharpe": 1.4,
            "avg_return": 0.085,
            "trade_efficiency": {"avg": 0.08},
            "filters": {"blocked_by_atr": 0.62, "blocked_by_art": 0.62},
            "top_configs": [{"rank": 1, "sharpe": 1.8, "return": 0.12, "params": {"z_entry": -1.4}}],
            "parameter_analysis": {
                "excursion_toggle": {
                    True: {"avg_sharpe": 1.7, "avg_return": 0.11, "num_runs": 2},
                    False: {"avg_sharpe": 1.1, "avg_return": 0.06, "num_runs": 2},
                },
                "excursion_min": {
                    0.008: {"avg_sharpe": 1.0, "avg_return": 0.05, "num_runs": 1},
                    0.01: {"avg_sharpe": 1.5, "avg_return": 0.095, "num_runs": 2},
                    0.015: {"avg_sharpe": 1.6, "avg_return": 0.10, "num_runs": 1},
                },
                "excursion_window": {
                    2.0: {"avg_sharpe": 1.0, "avg_return": 0.05, "num_runs": 1},
                    3.0: {"avg_sharpe": 1.5, "avg_return": 0.095, "num_runs": 2},
                    5.0: {"avg_sharpe": 1.6, "avg_return": 0.10, "num_runs": 1},
                },
            },
        }
    )

    assert "# Experiment Analysis Report" in report
    assert "## Parameter Contribution Analysis" in report
    assert "### 1. Excursion Filter (ON vs OFF)" in report
    assert "### 2. excursion_min Sensitivity" in report
    assert "### 3. excursion_window Sensitivity" in report
    assert "Excursion filter improves performance" in report
    assert "Best excursion_min is 0.01" in report
    assert "Smaller windows such as 2.0 are more reactive" in report
    assert "Strategy dominated by ATR filtering" in report


def test_report_and_analysis_handle_missing_fields(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "missing_fields"
    output_dir.mkdir(parents=True)
    (output_dir / "summary.csv").write_text("total_return,sharpe\n0.05,\n", encoding="utf-8")
    (output_dir / "summary_sorted.csv").write_text("total_return,sharpe\n0.05,\n", encoding="utf-8")

    run_dir = output_dir / "run_001"
    run_dir.mkdir()
    _write_json(run_dir / "metrics.json", {"rtot": 0.05})
    _write_json(run_dir / "diagnostics_summary.json", {})

    results = analyze_experiment(str(output_dir))
    report = generate_markdown_report(results)

    assert results["total_runs"] == 1
    assert results["avg_sharpe"] == 0.0
    assert results["trade_efficiency"]["avg"] == 0.0
    assert "## Recommendations" in report
    assert "## Parameter Contribution Analysis" in report


def test_cli_analyze_writes_report_with_parameter_analysis(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "cli_demo"
    _build_mock_experiment(output_dir)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(output_dir)])

    assert result.exit_code == 0
    report_path = output_dir / "analysis_report.md"
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Excursion Filter (ON vs OFF)" in report
    assert "excursion_min Sensitivity" in report
    assert "excursion_window Sensitivity" in report
    assert str(report_path) in result.output


def test_analyze_experiment_accepts_legacy_blocked_by_art_alias(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "legacy_art"
    output_dir.mkdir(parents=True)
    (output_dir / "summary.csv").write_text("z_entry,z_exit,use_art_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe\n-1.0,0.5,True,False,3,0.01,0.05,1.0\n", encoding="utf-8")
    (output_dir / "summary_sorted.csv").write_text("z_entry,z_exit,use_art_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe\n-1.0,0.5,True,False,3,0.01,0.05,1.0\n", encoding="utf-8")
    run_dir = output_dir / "run_001"
    run_dir.mkdir()
    _write_json(run_dir / "metrics.json", {"total_return": 0.05, "sharpe": 1.0})
    _write_json(run_dir / "diagnostics_summary.json", {"entry_signals": 10, "executed_trades": 2, "blocked_by_art": 5})
    _write_snapshot(run_dir / "config_snapshot.yaml", {"z_entry": -1.0, "z_exit": 0.5, "use_art_filter": True, "use_multi_day_excursion": False, "excursion_window": 3, "excursion_min": 0.01})

    results = analyze_experiment(str(output_dir))

    assert results["filters"]["blocked_by_atr"] == pytest.approx(0.5)
    assert results["filters"]["blocked_by_art"] == pytest.approx(0.5)
