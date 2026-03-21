from ashare.strategies.components.execution import (
    create_position_state,
    evaluate_exit_engine,
    export_trade_metrics,
    get_holding_bars,
    update_trade_metrics,
)


def test_position_state_tracks_holding_bars_and_mfe_mae() -> None:
    state = create_position_state(entry_price=100.0, entry_bar=10, anchor_price=104.0)
    update_trade_metrics(state, close=103.0, current_bar=12)
    update_trade_metrics(state, close=97.0, current_bar=14)
    assert get_holding_bars(state, 14) == 4
    metrics = export_trade_metrics(state)
    assert metrics["mfe"] == 0.03
    assert metrics["mae"] == -0.03
    assert metrics["mfe_pct"] == 0.03
    assert metrics["mae_pct"] == -0.03
    assert metrics["bars_to_mfe"] == 2
    assert metrics["bars_to_mae"] == 4
    assert metrics["mfe_price"] == 103.0
    assert metrics["mae_price"] == 97.0


def test_exit_engine_returns_recovery_then_max_hold_then_stop() -> None:
    state = create_position_state(entry_price=98.0, entry_bar=100, anchor_price=100.0)

    recovery = evaluate_exit_engine(
        close=99.0,
        current_bar=101,
        state=state,
        recovery_frac=0.5,
        take_profit_pct=0.05,
        stop_loss_pct=0.1,
        max_hold_bars=10,
    )
    assert recovery.signal is True
    assert recovery.reason == "anchor_recovery"
    assert recovery.effective_target_price == 99.0

    hold = evaluate_exit_engine(
        close=98.1,
        current_bar=110,
        state=state,
        recovery_frac=0.5,
        take_profit_pct=0.05,
        stop_loss_pct=0.1,
        max_hold_bars=10,
    )
    assert hold.signal is True
    assert hold.reason == "max_hold"

    stop = evaluate_exit_engine(
        close=88.0,
        current_bar=101,
        state=state,
        recovery_frac=0.5,
        take_profit_pct=0.05,
        stop_loss_pct=0.1,
        max_hold_bars=10,
    )
    assert stop.signal is True
    assert stop.reason == "stop_loss"
