from __future__ import annotations

import yaml
import pandas as pd
from click.testing import CliRunner

from ashare.cli import cli
from ashare.config.settings import BacktestConfig


class _DummyStrategy:
    params = {}


def _fake_df() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=4, freq="30min")
    return pd.DataFrame(
        {
            "open": [1.0, 1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0, 1.0],
            "volume": [100, 100, 100, 100],
        },
        index=idx,
    )


def test_experiment_yaml_only_uses_config_range(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)
    monkeypatch.setattr(
        "ashare.cli.load_experiment_spec",
        lambda _: {
            "name": "exp_yaml_only",
            "strategy": "dummy",
            "symbols": ["002850.SZ"],
            "start": "2024-01-01",
            "end": "2024-12-31",
            "parameters": {},
            "grid": {},
            "execution": {},
        },
    )

    called = {}

    def _fake_loader(ts_code, start_date, end_date):
        called["args"] = (ts_code, start_date, end_date)
        return _fake_df()

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0}),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["experiment", "spec.yaml"])

    assert result.exit_code == 0
    assert called["args"] == ("002850.SZ", "2024-01-01", "2024-12-31")
    assert "Date range: 2024-01-01 → 2024-12-31 (from config)" in result.output

    snapshot = yaml.safe_load((tmp_path / "outputs" / "exp_yaml_only" / "run_001" / "config_snapshot.yaml").read_text())
    assert snapshot["date_range"] == {"start": "2024-01-01", "end": "2024-12-31"}


def test_backtest_cli_override_dates_are_passed_to_loader(monkeypatch) -> None:
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)

    called = {}

    def _fake_loader(ts_code, start_date, end_date):
        called["args"] = (ts_code, start_date, end_date)
        return _fake_df()

    monkeypatch.setattr("ashare.cli.load_minute_30", _fake_loader)
    monkeypatch.setattr(
        "ashare.cli.run_backtest",
        lambda *args, **kwargs: (
            None,
            None,
            {"final_value": 100_000.0, "rtot": 0.02, "max_drawdown": 2.0, "num_trades": 1, "sharpe": None},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "backtest",
            "--symbol",
            "002850.SZ",
            "--strategy",
            "dummy",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
        ],
    )

    assert result.exit_code == 0
    assert called["args"] == ("002850.SZ", "2025-01-01", "2025-12-31")


def test_experiment_cli_override_takes_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)
    monkeypatch.setattr(
        "ashare.cli.load_experiment_spec",
        lambda _: {
            "name": "exp_override",
            "strategy": "dummy",
            "symbols": ["002850.SZ"],
            "start": "2024-01-01",
            "end": "2024-12-31",
            "parameters": {},
            "grid": {},
            "execution": {},
        },
    )

    called = {}

    def _fake_loader(ts_code, start_date, end_date):
        called["args"] = (ts_code, start_date, end_date)
        return _fake_df()

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0}),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["experiment", "spec.yaml", "--start", "2025-01-01", "--end", "2025-12-31"])

    assert result.exit_code == 0
    assert called["args"] == ("002850.SZ", "2025-01-01", "2025-12-31")
    assert "Date range: 2025-01-01 → 2025-12-31 (CLI override)" in result.output

    snapshot = yaml.safe_load((tmp_path / "outputs" / "exp_override" / "run_001" / "config_snapshot.yaml").read_text())
    assert snapshot["date_range"] == {"start": "2025-01-01", "end": "2025-12-31"}


def test_invalid_date_format_is_rejected() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["experiment", "spec.yaml", "--start", "20250101"])

    assert result.exit_code != 0
    assert "start must be YYYY-MM-DD" in result.output
