from click.testing import CliRunner
import pandas as pd
import yaml

from ashare.cli import cli
from ashare.config.settings import BacktestConfig


class _DummyStrategy:
    params = (
        ("z_entry", -1.0),
        ("z_exit", 0.2),
        ("use_art_filter", False),
    )


def _spec() -> dict:
    return {
        "name": "exp_param_flow",
        "strategy": "dummy",
        "symbols": ["002850.SZ"],
        "start": "2024-01-01",
        "end": "2024-12-31",
        "parameters": {"z_entry": -1.1, "use_art_filter": False},
        "grid": {"z_entry": [-1.2, -1.3], "z_exit": [0.3, 0.5]},
        "execution": {},
    }


def test_cli_param_and_date_overrides_have_highest_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)
    monkeypatch.setattr("ashare.cli.load_experiment_spec", lambda _: _spec())

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: pd.DataFrame({
        "open": [1.0, 1.0, 1.0],
        "high": [1.0, 1.0, 1.0],
        "low": [1.0, 1.0, 1.0],
        "close": [1.0, 1.0, 1.0],
        "volume": [100, 100, 100],
    }, index=pd.date_range("2024-01-01", periods=3, freq="D")))

    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0, "total_return": 0.01, "sharpe": 1.0}),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "spec.yaml",
            "--param",
            "z_entry=-1.5",
            "--param",
            "use_art_filter=true",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
        ],
    )

    assert result.exit_code == 0
    assert "Date range: 2025-01-01 → 2025-12-31 (CLI override)" in result.output

    run_dir = tmp_path / "outputs" / "exp_param_flow" / "run_001"
    snapshot = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text())
    assert snapshot["parameters"]["z_entry"] == -1.5
    assert snapshot["parameters"]["z_exit"] == 0.3
    assert snapshot["parameters"]["use_art_filter"] is True


def test_executor_logs_running_parameters(monkeypatch, caplog, tmp_path) -> None:
    from ashare.experiment.executor import execute_experiment_spec

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: pd.DataFrame({
        "open": [1.0, 1.0, 1.0],
        "high": [1.0, 1.0, 1.0],
        "low": [1.0, 1.0, 1.0],
        "close": [1.0, 1.0, 1.0],
        "volume": [100, 100, 100],
    }, index=pd.date_range("2024-01-01", periods=3, freq="D")))

    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0, "total_return": 0.01, "sharpe": 1.0}),
    )

    caplog.set_level("INFO", logger="ashare.experiment.executor")
    execute_experiment_spec(
        strategy_cls=_DummyStrategy,
        strategy_name="dummy",
        spec={
            "name": "exp_logging",
            "strategy": "dummy",
            "symbols": ["002850.SZ"],
            "start": "2024-01-01",
            "end": "2024-01-02",
            "parameters": {"use_art_filter": True},
            "grid": {"z_entry": [-1.5], "z_exit": [0.5]},
        },
        config=BacktestConfig(),
    )

    assert "Running: z_entry=-1.5, z_exit=0.5, use_art_filter=true" in caplog.text
