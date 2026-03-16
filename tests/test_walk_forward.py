import json
from pathlib import Path

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.research.walk_forward import generate_walk_forward_windows, run_walk_forward
from ashare.strategies.mid_freq_ma import MidFreqMA


def _synthetic_df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=800, freq="D")
    close = [10 + (i * 0.01) for i in range(800)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
            "volume": [1000] * 800,
            "turnover_rate": [2.0] * 800,
        },
        index=idx,
    )


def test_generate_walk_forward_windows_rolls_forward() -> None:
    windows = generate_walk_forward_windows(
        start_date="2020-01-01",
        end_date="2021-01-01",
        train_window=180,
        test_window=60,
    )

    assert len(windows) >= 2
    assert windows[0]["train_start"] == "2020-01-01"
    assert windows[0]["train_end"] == "2020-06-29"
    assert windows[0]["test_start"] == "2020-06-29"
    assert windows[0]["test_end"] == "2020-08-28"
    assert windows[1]["train_start"] == "2020-03-01"


def test_run_walk_forward_creates_result_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ashare.research.walk_forward.load_minute_30", lambda *args, **kwargs: _synthetic_df())

    result = run_walk_forward(
        strategy_cls=MidFreqMA,
        symbol="600519.SH",
        param_grid={"short_period": [3, 5], "long_period": [8], "turnover_thresh": [1.0]},
        start_date="2020-01-01",
        end_date="2020-12-31",
        train_window=120,
        test_window=30,
        config=BacktestConfig(),
    )

    results_path = Path(result["results_path"])
    summary_path = Path(result["summary_path"])
    windows_path = Path(result["windows_path"])

    assert results_path.exists()
    assert summary_path.exists()
    assert windows_path.exists()

    results_df = pd.read_csv(results_path)
    assert not results_df.empty
    assert set(
        [
            "symbol",
            "train_start",
            "train_end",
            "test_start",
            "test_end",
            "best_parameters",
            "test_return",
            "test_sharpe",
            "test_drawdown",
        ]
    ).issubset(results_df.columns)

    first_params = json.loads(results_df.iloc[0]["best_parameters"])
    assert "short_period" in first_params

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["num_windows"] >= 1
