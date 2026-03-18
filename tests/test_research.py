from __future__ import annotations

import json

from click.testing import CliRunner

from ashare.cli import cli
from ashare.research import analyze_experiment, generate_markdown_report


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_mock_experiment(output_dir) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.csv").write_text(
        "z_entry,z_exit,use_art_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe,max_drawdown,num_trades\n"
        "-1.2,0.3,True,False,3,0.01,0.12,1.8,4.0,6\n"
        "-1.5,0.5,False,True,5,0.02,0.08,1.2,5.0,4\n",
        encoding="utf-8",
    )
    (output_dir / "summary_sorted.csv").write_text(
        "z_entry,z_exit,use_art_filter,use_multi_day_excursion,excursion_window,excursion_min,total_return,sharpe,max_drawdown,num_trades\n"
        "-1.2,0.3,True,False,3,0.01,0.12,1.8,4.0,6\n"
        "-1.5,0.5,False,True,5,0.02,0.08,1.2,5.0,4\n",
        encoding="utf-8",
    )

    run_1 = output_dir / "run_001"
    run_1.mkdir()
    _write_json(
        run_1 / "metrics.json",
        {"total_return": 0.12, "sharpe": 1.8},
    )
    _write_json(
        run_1 / "diagnostics_summary.json",
        {"entry_signals": 10, "executed_trades": 2, "blocked_by_art": 6, "blocked_by_excursion": 1},
    )

    run_2 = output_dir / "run_002"
    run_2.mkdir()
    _write_json(
        run_2 / "metrics.json",
        {"total_return": 0.08, "sharpe": 1.2},
    )
    _write_json(
        run_2 / "diagnostics_summary.json",
        {"entry_signals": 5, "executed_trades": 1, "blocked_by_art": 1, "blocked_by_excursion": 3},
    )


def test_analyze_experiment_aggregates_metrics_correctly(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "demo"
    _build_mock_experiment(output_dir)

    results = analyze_experiment(str(output_dir))

    assert results["total_runs"] == 2
    assert results["best_sharpe"] == 1.8
    assert results["best_return"] == 0.12
    assert results["avg_sharpe"] == 1.5
    assert results["avg_return"] == 0.1
    assert results["trade_efficiency"]["avg"] == 0.2
    assert results["filters"]["blocked_by_art"] == 0.4
    assert results["filters"]["blocked_by_excursion"] == 0.35
    assert results["top_configs"][0]["rank"] == 1
    assert results["top_configs"][0]["params"]["z_entry"] == -1.2


def test_generate_markdown_report_contains_key_sections() -> None:
    report = generate_markdown_report(
        {
            "total_runs": 2,
            "best_sharpe": 1.8,
            "best_return": 0.12,
            "avg_sharpe": 1.5,
            "avg_return": 0.1,
            "trade_efficiency": {"avg": 0.05},
            "filters": {"blocked_by_art": 0.6, "blocked_by_excursion": 0.55},
            "top_configs": [{"rank": 1, "sharpe": 1.8, "return": 0.12, "params": {"z_entry": -1.2}}],
        }
    )

    assert "# Experiment Analysis Report" in report
    assert "## Summary" in report
    assert "## Top Configurations" in report
    assert "## Trade Efficiency" in report
    assert "## Filter Impact" in report
    assert "## Insights" in report
    assert "Strategy over-filtered" in report
    assert "ART filter too restrictive" in report
    assert "Excursion filter limiting signals" in report


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


def test_cli_analyze_writes_report(tmp_path) -> None:
    output_dir = tmp_path / "outputs" / "cli_demo"
    _build_mock_experiment(output_dir)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(output_dir)])

    assert result.exit_code == 0
    report_path = output_dir / "analysis_report.md"
    assert report_path.exists()
    assert str(report_path) in result.output
