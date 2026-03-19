import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.shock_reversion_intraday import ShockReversionIntradayStrategy


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


def _run(closes: list[float], strategy_params: dict) -> ShockReversionIntradayStrategy:
    _, strat, _ = run_backtest(
        strategy_cls=ShockReversionIntradayStrategy,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"trend_ma_period": 2, **strategy_params},
        symbol="SYNTH",
    )
    return strat


def test_shock_reversion_enters_on_excursion_signal() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "max_hold_only",
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert strat.buy_events >= 1
    assert strat.position.size > 0


def test_shock_reversion_trend_filter_blocks_entry() -> None:
    closes = [100.0] * 180 + [95.0, 95.0, 95.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": True,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "max_hold_only",
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_shock_reversion_fixed_take_profit_exit() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 100.0, 100.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "fixed_tp",
            "take_profit_pct": 0.02,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert len(strat.completed_trades) == 1
    assert strat.completed_trades[0]["exit_reason"] == "take_profit"
    assert strat.completed_trades[0]["exit_subtype"] == "take_profit"
    assert strat.completed_trades[0]["exit_price"] == 100.0


def test_shock_reversion_anchor_recovery_exit_uses_frozen_anchor() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 99.0, 99.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "anchor_recovery",
            "recovery_frac": 0.5,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert len(strat.completed_trades) == 1
    trade = strat.completed_trades[0]
    assert trade["anchor_price_at_entry"] == 100.0
    assert trade["excursion_at_entry"] == -0.03
    assert trade["recovery_target"] == 99.0
    assert round(trade["take_profit_price"], 2) == 99.96
    assert trade["effective_target_price"] == 99.0
    assert trade["exit_reason"] == "recovery"
    assert trade["exit_subtype"] == "recovery"
    assert trade["exit_price"] == 99.0


def test_shock_reversion_max_hold_remains_safeguard() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 98.0, 98.0, 98.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "fixed_tp",
            "take_profit_pct": 0.05,
            "max_hold_bars": 2,
            "stop_loss_pct": 0.10,
        },
    )

    assert len(strat.completed_trades) == 1
    assert strat.completed_trades[0]["exit_reason"] == "max_hold"


def test_shock_reversion_records_completed_trade_stats_and_signals() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 99.0, 99.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "exit_mode": "anchor_recovery",
            "recovery_frac": 0.5,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert len(strat.completed_trades) == 1
    trade = strat.completed_trades[0]
    assert trade["symbol"] == "SYNTH"
    assert trade["holding_bars"] == 2
    assert trade["entry_price"] == 98.0
    assert trade["exit_price"] == 99.0
    assert trade["pnl_pct"] > 0
    assert trade["mfe_pct"] == trade["max_favorable_excursion"]
    assert trade["mae_pct"] == trade["max_adverse_excursion"]
    assert trade["max_favorable_excursion"] >= trade["pnl_pct"]
    assert trade["max_adverse_excursion"] <= 0.0
    assert trade["bars_to_mfe"] >= 1
    assert trade["bars_to_mae"] == 0
    assert strat.signal_events
    assert all({"datetime", "excursion", "threshold", "trend_ok", "entry_executed"} <= row.keys() for row in strat.signal_events)
