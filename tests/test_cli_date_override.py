from __future__ import annotations

import yaml
import pandas as pd
from click.testing import CliRunner


def _timestamped_output_dir(tmp_path, base_name: str):
    matches = sorted((tmp_path / "outputs" / base_name).glob(f"*_{base_name}"))
    assert matches, f"No timestamped output directory found for {base_name}"
    return matches[-1]

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

    output_root = _timestamped_output_dir(tmp_path, "exp_yaml_only")
    snapshot = yaml.safe_load((output_root / "run_001" / "config_snapshot.yaml").read_text())
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

    output_root = _timestamped_output_dir(tmp_path, "exp_override")
    snapshot = yaml.safe_load((output_root / "run_001" / "config_snapshot.yaml").read_text())
    assert snapshot["date_range"] == {"start": "2025-01-01", "end": "2025-12-31"}


def test_invalid_date_format_is_rejected() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["experiment", "spec.yaml", "--start", "20250101"])

    assert result.exit_code != 0
    assert "start must be YYYY-MM-DD" in result.output


def test_data_fetch_ohlcv_daily_writes_expected_csv(monkeypatch, tmp_path) -> None:
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    source = pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.8, 10.8],
            "close": [10.2, 11.2],
            "volume": [1000, 1100],
            "turnover_rate": [1.0, 1.1],
        },
        index=idx,
    )

    called = {}

    def _fake_load_daily(ts_code, start_date, end_date, use_cache=True):
        called["args"] = (ts_code, start_date, end_date, use_cache)
        return source

    monkeypatch.setattr("ashare.cli.load_daily", _fake_load_daily)

    runner = CliRunner()
    output_dir = tmp_path / "ohlcv"
    result = runner.invoke(
        cli,
        [
            "data",
            "fetch-ohlcv",
            "--tickers",
            "002850.SZ",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--timeframe",
            "daily",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert called["args"] == ("002850.SZ", "2024-01-01", "2024-01-31", True)
    written = pd.read_csv(output_dir / "002850.SZ.csv")
    assert list(written.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert len(written) == 2
    assert "[OK] 002850.SZ | daily | 2 rows" in result.output


def test_data_fetch_ohlcv_continues_on_ticker_error(monkeypatch, tmp_path) -> None:
    idx = pd.to_datetime(["2024-01-01"])
    good = pd.DataFrame(
        {
            "open": [10.0],
            "high": [10.5],
            "low": [9.8],
            "close": [10.2],
            "volume": [1000],
            "turnover_rate": [1.0],
        },
        index=idx,
    )

    def _fake_load_daily(ts_code, start_date, end_date, use_cache=True):
        if ts_code == "BAD.SZ":
            raise ValueError("invalid ticker")
        return good

    monkeypatch.setattr("ashare.cli.load_daily", _fake_load_daily)

    runner = CliRunner()
    output_dir = tmp_path / "ohlcv"
    result = runner.invoke(
        cli,
        [
            "data",
            "fetch-ohlcv",
            "--tickers",
            "BAD.SZ",
            "--tickers",
            "000001.SZ",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--timeframe",
            "daily",
            "--output-dir",
            str(output_dir),
            "--no-cache",
        ],
    )

    assert result.exit_code == 0
    assert "[ERROR] BAD.SZ invalid ticker" in result.output
    assert "[OK] 000001.SZ | daily | 1 rows" in result.output
    assert (output_dir / "000001.SZ.csv").exists()


def test_data_fetch_ohlcv_auto_run_regime(monkeypatch, tmp_path) -> None:
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    source = pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.8, 10.8],
            "close": [10.2, 11.2],
            "volume": [1000, 1100],
            "turnover_rate": [1.0, 1.1],
        },
        index=idx,
    )

    monkeypatch.setattr("ashare.cli.load_daily", lambda *args, **kwargs: source)
    called = {}

    def _fake_runner(*, tickers, input_dir, output_dir):
        called["args"] = (tickers, input_dir, output_dir)

    monkeypatch.setattr("ashare.cli._load_regime_backtest_runner", lambda: _fake_runner)

    runner = CliRunner()
    output_dir = tmp_path / "ohlcv"
    regime_dir = tmp_path / "regime"
    result = runner.invoke(
        cli,
        [
            "data",
            "fetch-ohlcv",
            "--tickers",
            "002850.SZ",
            "--tickers",
            "000001.SZ",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--timeframe",
            "daily",
            "--output-dir",
            str(output_dir),
            "--auto-run-regime",
            "--regime-output-dir",
            str(regime_dir),
        ],
    )

    assert result.exit_code == 0
    assert called["args"][0] == ["000001.SZ", "002850.SZ"]
    assert called["args"][1] == output_dir
    assert called["args"][2] == regime_dir
    assert "[PIPELINE] Running regime classification..." in result.output
    assert "[PIPELINE] Completed" in result.output


def test_data_fetch_ohlcv_skips_regime_when_no_successful_tickers(monkeypatch, tmp_path) -> None:
    def _raise_loader(*args, **kwargs):
        raise ValueError("invalid ticker")

    monkeypatch.setattr("ashare.cli.load_daily", _raise_loader)

    def _fake_runner(*, tickers, input_dir, output_dir):
        raise AssertionError("Runner should not be called")

    monkeypatch.setattr("ashare.cli._load_regime_backtest_runner", lambda: _fake_runner)

    runner = CliRunner()
    output_dir = tmp_path / "ohlcv"
    result = runner.invoke(
        cli,
        [
            "data",
            "fetch-ohlcv",
            "--tickers",
            "BAD.SZ",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--timeframe",
            "daily",
            "--output-dir",
            str(output_dir),
            "--auto-run-regime",
        ],
    )

    assert result.exit_code == 0
    assert "[WARN] Skipping regime run: no successfully fetched ticker CSVs." in result.output
