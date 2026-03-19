"""Minimal shared execution helpers for strategy order state and exits."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass
class PositionState:
    """Stable per-position execution state shared across strategies."""

    entry_price: float
    entry_bar: int
    anchor_price: float | None = None
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    bars_to_mfe: int = 0
    bars_to_mae: int = 0


@dataclass
class ExitDecision:
    """Result of evaluating shared execution exits."""

    signal: bool
    reason: str | None
    holding_bars: int
    recovery_target: float | None
    take_profit_price: float | None
    effective_target_price: float | None


def create_position_state(entry_price: float, entry_bar: int, anchor_price: float | None = None) -> PositionState:
    """Create the initial execution state for a new position."""
    return PositionState(entry_price=float(entry_price), entry_bar=int(entry_bar), anchor_price=anchor_price)


def get_holding_bars(state: PositionState, current_bar: int) -> int:
    """Return elapsed bars since entry."""
    return max(0, int(current_bar) - int(state.entry_bar))


def update_trade_metrics(state: PositionState, close: float, current_bar: int) -> None:
    """Update shared MFE/MAE metrics for an open position."""
    holding_bars = get_holding_bars(state, current_bar)
    move_pct = ((float(close) - float(state.entry_price)) / float(state.entry_price)) * 100.0
    if move_pct > state.mfe_pct:
        state.mfe_pct = move_pct
        state.max_favorable_excursion = move_pct
        state.bars_to_mfe = holding_bars
    if move_pct < state.mae_pct:
        state.mae_pct = move_pct
        state.max_adverse_excursion = move_pct
        state.bars_to_mae = holding_bars


def export_trade_metrics(state: PositionState) -> dict[str, Any]:
    """Return stable execution metrics for persistence/diagnostics."""
    return {
        "entry_price": float(state.entry_price),
        "anchor_price_at_entry": None if state.anchor_price is None else float(state.anchor_price),
        "mfe_pct": float(state.mfe_pct),
        "mae_pct": float(state.mae_pct),
        "max_favorable_excursion": float(state.max_favorable_excursion),
        "max_adverse_excursion": float(state.max_adverse_excursion),
        "bars_to_mfe": int(state.bars_to_mfe),
        "bars_to_mae": int(state.bars_to_mae),
    }


def _build_exit_targets(
    *,
    entry_price: float,
    anchor_price: float | None,
    recovery_frac: float | None,
    take_profit_pct: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Return recovery, take-profit, and effective exit targets."""
    recovery_target = None
    if anchor_price is not None and recovery_frac is not None:
        shock_depth = max(0.0, float(anchor_price) - float(entry_price))
        recovery_target = float(entry_price) + (float(recovery_frac) * shock_depth)

    take_profit_price = None
    if take_profit_pct is not None:
        take_profit_price = float(entry_price) * (1.0 + float(take_profit_pct))

    targets = [target for target in (recovery_target, take_profit_price) if target is not None]
    effective_target_price = min(targets) if targets else None
    return recovery_target, take_profit_price, effective_target_price


def evaluate_exit_engine(
    *,
    close: float,
    current_bar: int,
    state: PositionState | None,
    recovery_frac: float | None,
    take_profit_pct: float | None,
    stop_loss_pct: float | None,
    max_hold_bars: int | None,
) -> ExitDecision:
    """Evaluate shared execution exits for an open position."""
    if state is None:
        return ExitDecision(
            signal=False,
            reason=None,
            holding_bars=0,
            recovery_target=None,
            take_profit_price=None,
            effective_target_price=None,
        )

    recovery_target, take_profit_price, effective_target_price = _build_exit_targets(
        entry_price=state.entry_price,
        anchor_price=state.anchor_price,
        recovery_frac=recovery_frac,
        take_profit_pct=take_profit_pct,
    )
    holding_bars = get_holding_bars(state, current_bar)

    if stop_loss_pct is not None and float(close) <= float(state.entry_price) * (1.0 - float(stop_loss_pct)):
        return ExitDecision(True, "stop_loss", holding_bars, recovery_target, take_profit_price, effective_target_price)

    if effective_target_price is not None and float(close) >= float(effective_target_price):
        if take_profit_price is not None and math.isclose(float(effective_target_price), float(take_profit_price)):
            return ExitDecision(True, "take_profit", holding_bars, recovery_target, take_profit_price, effective_target_price)
        return ExitDecision(True, "anchor_recovery", holding_bars, recovery_target, take_profit_price, effective_target_price)

    if max_hold_bars is not None and holding_bars >= int(max_hold_bars):
        return ExitDecision(True, "max_hold", holding_bars, recovery_target, take_profit_price, effective_target_price)

    return ExitDecision(False, None, holding_bars, recovery_target, take_profit_price, effective_target_price)
