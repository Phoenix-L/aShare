"""Strategy signal tests (logic-only)."""

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.mean_reversion_advanced import MeanReversionAdvanced


def _synthetic_df(closes: list[float], spread: float = 1.0) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="30min")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
            "turnover_rate": [2.0] * len(closes),
        },
        index=idx,
    )


def _run(closes: list[float], strategy_params: dict, spread: float = 1.0) -> MeanReversionAdvanced:
    # MeanReversionAdvanced now computes MA20/MA120 from a daily-resampled view
    # (and uses previous completed daily bars). Keep windows small for the
    # synthetic horizon used in these tests.
    strategy_params = {"ma_short": 2, "ma_trend": 2, **strategy_params}
    _, strat, _ = run_backtest(
        strategy_cls=MeanReversionAdvanced,
        data_df=_synthetic_df(closes, spread=spread),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params=strategy_params,
        symbol="SYNTH",
    )
    return strat


def test_multi_day_excursion_filter_blocks_trade_when_excursion_too_small() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": True,
            "excursion_window": 3,
            "excursion_min": 0.03,
        },
        spread=0.01,
    )

    assert strat.buy_events == 0
    assert any("excursion_filter" in row["blocked_by"] for row in strat.diagnostics if row["entry_signal"])


def test_multi_day_excursion_filter_allows_trade_when_excursion_threshold_is_met() -> None:
    closes = [100.0] * 180 + [97.0, 97.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": True,
            "excursion_window": 3,
            "excursion_min": 0.01,
        },
        spread=1.0,
    )

    assert strat.buy_events >= 1
    assert any(row["executed"] and row["excursion_ok"] for row in strat.diagnostics)


def test_atr_and_legacy_art_filter_params_behave_the_same() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    strat_atr = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": True,
        },
        spread=0.01,
    )
    strat_art = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_art_filter": True,
        },
        spread=0.01,
    )

    assert strat_atr.buy_events == 0
    assert strat_art.buy_events == 0
