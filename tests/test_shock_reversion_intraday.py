import pandas as pd
import pytest

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.components.execution import create_position_state, evaluate_exit_engine
from ashare.strategies.components.shock_score import compute_shock_score
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


def _session_df(start: str, end: str, close: float = 100.0, spread: float = 1.0) -> pd.DataFrame:
    days = pd.bdate_range(start, end)
    idx = []
    for day in days:
        for time_str in ["10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00"]:
            idx.append(pd.Timestamp(f"{day.date()} {time_str}"))

    closes = [close] * len(idx)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
            "turnover_rate": [2.0] * len(closes),
        },
        index=pd.DatetimeIndex(idx),
    )


def _run(closes: list[float], strategy_params: dict) -> ShockReversionIntradayStrategy:
    _, strat, _ = run_backtest(
        strategy_cls=ShockReversionIntradayStrategy,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params=strategy_params,
        symbol="SYNTH",
    )
    return strat




def test_compute_shock_score_v1_breakdown_matches_formula() -> None:
    breakdown = compute_shock_score(
        close_now=95.0,
        close_prev=94.0,
        close_minus_two=100.0,
        high_now=96.0,
        low_now=93.0,
        excursion=-0.05,
        excursion_threshold=0.02,
        close_history=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 94.0, 95.0],
    )

    assert breakdown.depth_raw == pytest.approx(0.05)
    assert breakdown.depth_score == 1.0
    assert breakdown.speed_ret == pytest.approx(-0.05)
    assert breakdown.speed_score == 1.0
    assert breakdown.stabilization_score == 1.0
    assert breakdown.noise_base > 0
    assert breakdown.noise_penalty == 0.0
    assert breakdown.shock_score == pytest.approx(90.0)


def test_shock_reversion_signal_events_include_score_breakdown() -> None:
    closes = [100.0] * 180 + [95.0, 96.0, 97.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "max_hold_bars": 10, "stop_loss_pct": 0.10})

    signal = strat.signal_events[0]
    for key in [
        "excursion",
        "depth_raw",
        "depth_score",
        "speed_ret",
        "speed_score",
        "stabilization_score",
        "noise_base",
        "noise_ratio",
        "noise_penalty",
        "shock_score",
        "shock_score_min",
        "shock_score_filter_enabled",
        "blocked_by_shock_score",
        "entry_executed",
    ]:
        assert key in signal
    assert signal["shock_score"] >= 0.0


def test_shock_reversion_optional_score_filter_blocks_low_score_entries() -> None:
    closes = [100.0] * 180 + [99.0, 99.0, 99.0]
    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.005,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
            "use_shock_score_filter": True,
            "shock_score_min": 60,
        },
    )

    assert strat.buy_events == 0
    blocked = [row for row in strat.diagnostics if row["entry_signal"] and not row["executed"]]
    assert blocked
    assert any(row["blocked_by_shock_score"] for row in blocked)
    assert any("shock_score_filter" in row["blocked_by"] for row in blocked)
    assert all(row["shock_score_filter_enabled"] for row in blocked)


def test_shock_reversion_trade_records_include_score_at_entry() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 100.0, 100.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 1.0, "max_hold_bars": 10, "stop_loss_pct": 0.10})

    assert strat.completed_trades[0]["shock_score_at_entry"] >= 0.0

def test_shock_reversion_enters_on_excursion_signal() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "max_hold_bars": 10, "stop_loss_pct": 0.10})
    assert strat.buy_events >= 1
    assert strat.position.size > 0


def test_shock_reversion_entry_depends_only_on_excursion_signal() -> None:
    closes = [100.0] * 180 + [95.0, 95.0, 95.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "max_hold_bars": 10, "stop_loss_pct": 0.10})
    assert strat.buy_events >= 1
    assert all("trend_ok" not in row for row in strat.diagnostics)
    assert all("trend_filter" not in row.get("blocked_by", []) for row in strat.diagnostics)
    assert all("atr_filter" not in row.get("blocked_by", []) for row in strat.diagnostics)


def test_shock_reversion_take_profit_exit() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 100.0, 100.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 1.0, "max_hold_bars": 10, "stop_loss_pct": 0.10})
    assert len(strat.completed_trades) == 1
    assert strat.completed_trades[0]["exit_reason"] == "take_profit"


def test_shock_reversion_profit_exit_uses_first_target_hit() -> None:
    state = create_position_state(entry_price=97.0, entry_bar=10, anchor_price=100.0)
    exit_plan = evaluate_exit_engine(
        close=99.0,
        current_bar=11,
        state=state,
        recovery_frac=1.0,
        take_profit_pct=0.02,
        stop_loss_pct=0.10,
        max_hold_bars=10,
    )
    assert exit_plan.take_profit_price < exit_plan.recovery_target
    assert exit_plan.effective_target_price == exit_plan.take_profit_price
    assert exit_plan.reason == "take_profit"
    assert exit_plan.signal is True


def test_shock_reversion_recovery_exit_uses_frozen_anchor() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 99.0, 99.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 0.5, "max_hold_bars": 10, "stop_loss_pct": 0.10})
    assert len(strat.completed_trades) == 1
    trade = strat.completed_trades[0]
    assert trade["anchor_price_at_entry"] == 100.0
    assert trade["exit_reason"] == "recovery"
    assert trade["effective_target_price"] == 99.0


def test_shock_reversion_tracks_etd_from_peak_to_exit() -> None:
    closes = [100.0] * 180 + [97.0, 99.5, 99.0, 99.0, 99.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 1.0, "take_profit_pct": 0.05, "max_hold_bars": 2, "stop_loss_pct": 0.10})
    assert len(strat.completed_trades) == 1
    trade = strat.completed_trades[0]
    assert trade["mfe_price"] == 99.5
    assert trade["exit_price"] == 99.0
    assert trade["etd"] == pytest.approx((trade["mfe_price"] - trade["exit_price"]) / trade["entry_price"])
    assert trade["etd"] >= 0.0


def test_shock_reversion_etd_is_zero_when_exit_matches_peak() -> None:
    closes = [100.0] * 180 + [97.0, 99.0, 99.5, 99.5, 99.5]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 0.5, "max_hold_bars": 10, "stop_loss_pct": 0.10})
    assert len(strat.completed_trades) == 1
    trade = strat.completed_trades[0]
    assert trade["mfe_price"] == trade["exit_price"]
    assert trade["etd"] == 0.0


def test_shock_reversion_max_hold_remains_safeguard() -> None:
    closes = [100.0] * 180 + [97.0, 98.0, 98.0, 98.0, 98.0]
    strat = _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.05, "max_hold_bars": 2, "stop_loss_pct": 0.10})
    assert len(strat.completed_trades) == 1
    assert strat.completed_trades[0]["exit_reason"] == "max_hold"


def test_shock_reversion_rejects_zscore_params() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0]
    with pytest.raises(ValueError, match="does not accept z-score params"):
        _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "z_entry": -1.0})


def test_shock_reversion_rejects_removed_trend_filter_params() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0]
    with pytest.raises(ValueError, match="does not accept use_trend_filter"):
        _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "use_trend_filter": False})
    with pytest.raises(ValueError, match="does not accept trend_ma_period"):
        _run(closes, {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "trend_ma_period": 120})


def test_shock_reversion_requires_only_intraday_excursion_history() -> None:
    df = _session_df("2026-02-24", "2026-02-28")

    _, strat, metrics = run_backtest(
        strategy_cls=ShockReversionIntradayStrategy,
        data_df=df,
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={
            "trade_unit": 500,
            "excursion_lookback_bars": 12,
            "excursion_threshold": 0.03,
            "recovery_frac": 0.5,
            "max_hold_bars": 40,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.03,
        },
        symbol="SYNTH",
    )

    assert len(strat.diagnostics) > 0
    assert metrics["diagnostics_summary"]["total_bars"] > 0
