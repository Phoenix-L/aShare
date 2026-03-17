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
    _, strat, _ = run_backtest(
        strategy_cls=MeanReversionAdvanced,
        data_df=_synthetic_df(closes, spread=spread),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params=strategy_params,
        symbol="SYNTH",
    )
    return strat


def test_advanced_mean_reversion_entry_and_exit_trigger() -> None:
    closes = [100.0] * 180 + [97.0, 101.0, 101.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 0.3,
            "use_trend_filter": False,
            "use_art_filter": False,
        },
    )

    assert strat.buy_events >= 1
    assert strat.sell_events >= 1
    assert strat.position.size == 0


def test_advanced_mean_reversion_trend_filter_blocks_entry() -> None:
    closes = [100.0] * 180 + [95.0, 95.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 5.0,
            "use_trend_filter": True,
            "use_art_filter": False,
        },
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_advanced_mean_reversion_art_filter_blocks_low_volatility_entry() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    strat = _run(
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

    assert strat.buy_events == 0
    assert strat.position.size == 0
