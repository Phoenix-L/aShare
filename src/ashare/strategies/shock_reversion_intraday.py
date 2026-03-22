"""Intraday shock-reversion strategy using close excursion from a rolling high."""

import math

import pandas as pd

import backtrader as bt

from ashare.strategies.components.execution import (
    create_position_state,
    evaluate_exit_engine,
    export_trade_metrics,
    update_trade_metrics,
)
from ashare.strategies.components.shock_score import DEFAULT_SCORE_WEIGHTS, compute_shock_score
from ashare.utils.logging import get_logger

logger = get_logger("ashare.strategies.shock_reversion_intraday")


class ShockReversionIntradayStrategy(bt.Strategy):
    """Standalone intraday shock-reversion strategy."""

    uses_trend_filter = False
    uses_atr_filter = False

    params = dict(
        trade_unit=500,
        enable_ladder=False,
        enable_ladder_simulation=False,
        ladder_min_drop_pct=0.02,
        ladder_min_bars_between_legs=1,
        ladder_score_min_add=0.0,
        max_legs=1,
        use_margin=False,
        margin_rate_annual=0.0835,
        bars_per_day=8,
        excursion_lookback_bars=3,
        excursion_threshold=0.01,
        take_profit_pct=0.02,
        recovery_frac=0.5,
        max_hold_bars=16,
        stop_loss_pct=0.02,
        speed_scale=0.03,
        noise_lookback=10,
        noise_ratio_scale=3.0,
        score_weight_depth=DEFAULT_SCORE_WEIGHTS["depth"],
        score_weight_speed=DEFAULT_SCORE_WEIGHTS["speed"],
        score_weight_stabilization=DEFAULT_SCORE_WEIGHTS["stabilization"],
        score_weight_noise_penalty=DEFAULT_SCORE_WEIGHTS["noise_penalty"],
        use_shock_score_filter=False,
        shock_score_min=60,
        shock_score_max=None,
    )

    @classmethod
    def validate_data_history(cls, data_df: pd.DataFrame, params: dict | None = None) -> None:
        """Fail fast when the requested window cannot satisfy required warm-up."""
        defaults = cls.params
        if hasattr(defaults, "_getitems"):
            resolved = dict(defaults._getitems())
        else:
            resolved = dict(defaults)
        resolved.update(params or {})

        intraday_bars = len(data_df)
        required_intraday_bars = int(resolved["excursion_lookback_bars"])
        if intraday_bars < required_intraday_bars:
            raise ValueError(
                "ShockReversionIntradayStrategy requires at least "
                f"{required_intraday_bars} intraday bars for excursion warm-up, got {intraday_bars}."
            )

    def __init__(self) -> None:
        if self.p.excursion_lookback_bars is None:
            raise ValueError("Invalid config: excursion_lookback_bars required")
        if int(self.p.bars_per_day) <= 0:
            raise ValueError("Invalid config: bars_per_day must be positive")

        self.rolling_max_close = bt.indicators.Highest(self.data.close, period=self.p.excursion_lookback_bars)
        self.excursion = (self.data.close - self.rolling_max_close) / self.rolling_max_close
        self.score_weights = {
            "depth": float(self.p.score_weight_depth),
            "speed": float(self.p.score_weight_speed),
            "stabilization": float(self.p.score_weight_stabilization),
            "noise_penalty": float(self.p.score_weight_noise_penalty),
        }

        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.completed_trades: list[dict] = []
        self.signal_events: list[dict] = []
        self.current_trade_reason: dict | None = None
        self.current_trade_record: dict | None = None
        self.position_state = None
        self.pending_entry_context: dict | None = None
        self.pending_exit_reason: str | None = None
        self.active_order = None
        self.total_margin_interest_paid = 0.0
        self.margin_interest_events: list[dict] = []
        self.min_cash = float(self.broker.getcash())
        self.current_legs = 0
        self.entry_prices: list[float] = []
        self.entry_sizes: list[int] = []
        self.anchor_prices: list[float] = []
        self.sim_legs_count = 0
        self.sim_entry_prices: list[float] = []
        self.sim_entry_sizes: list[int] = []
        self.sim_anchor_prices: list[float] = []
        self.sim_last_entry_bar = -1

    def _per_bar_margin_rate(self) -> float:
        """Return per-bar interest rate implied by annual margin cost."""
        daily_rate = float(self.p.margin_rate_annual) / 252.0
        return daily_rate / float(self.p.bars_per_day)

    def _apply_margin_interest(self) -> None:
        """Deduct borrowing cost whenever the cash balance is negative."""
        cash_before = float(self.broker.getcash())
        self.min_cash = min(self.min_cash, cash_before)
        if not self.p.use_margin or cash_before >= 0.0:
            return

        interest_cost = abs(cash_before) * self._per_bar_margin_rate()
        if interest_cost <= 0.0:
            return

        charge_cash = getattr(self.broker, "charge_cash", None)
        if callable(charge_cash):
            charge_cash(interest_cost)
        else:
            self.broker.add_cash(-interest_cost)
            refresh_value = getattr(self.broker, "_get_value", None)
            if callable(refresh_value):
                refresh_value()

        cash_after = float(self.broker.getcash())
        self.total_margin_interest_paid += interest_cost
        self.min_cash = min(self.min_cash, cash_after)
        self.margin_interest_events.append(
            {
                "datetime": self._current_datetime(),
                "cash_before": cash_before,
                "cash_after": cash_after,
                "interest_cost": interest_cost,
            }
        )

    def _get_symbol(self) -> str:
        """Return the current primary symbol name."""
        if getattr(self.data, "_name", None):
            return str(self.data._name)
        data_name = getattr(getattr(self.data, "p", None), "name", None)
        if data_name:
            return str(data_name)
        return "UNKNOWN"

    def _current_datetime(self) -> str:
        """Return the current bar datetime as ISO string."""
        return self.datas[0].datetime.datetime(0).isoformat()

    def _standardize_exit_reason(self, reason: str | None) -> str:
        """Return a stable exit reason label for diagnostics/export."""
        if reason == "anchor_recovery":
            return "recovery"
        if reason == "take_profit":
            return "take_profit"
        if reason == "stop_loss":
            return "stop_loss"
        if reason == "max_hold":
            return "max_hold"
        return "unknown"

    def _reset_ladder_state(self) -> None:
        """Reset per-trade ladder diagnostics."""
        self.current_legs = 0
        self.entry_prices = []
        self.entry_sizes = []
        self.anchor_prices = []

    def _reset_sim_ladder_state(self) -> None:
        """Reset per-trade ladder simulation state."""
        self.sim_legs_count = 0
        self.sim_entry_prices = []
        self.sim_entry_sizes = []
        self.sim_anchor_prices = []
        self.sim_last_entry_bar = -1

    def _record_leg(self, *, entry_price: float, size: int, anchor_price: float) -> None:
        """Track one executed entry leg for trade-level ladder diagnostics."""
        if self.current_legs == 0:
            self._reset_ladder_state()
        self.current_legs += 1
        self.entry_prices.append(float(entry_price))
        self.entry_sizes.append(int(size))
        self.anchor_prices.append(float(anchor_price))

    def _initialize_sim_trade_state(self, *, entry_price: float, size: int, anchor_price: float, current_bar: int) -> None:
        """Seed ladder simulation with the real first entry."""
        self.sim_legs_count = 1
        self.sim_entry_prices = [float(entry_price)]
        self.sim_entry_sizes = [int(size)]
        self.sim_anchor_prices = [float(anchor_price)]
        self.sim_last_entry_bar = int(current_bar)

    def _compute_sim_position_metrics(self) -> tuple[float, float, int]:
        """Return simulated average entry, effective anchor, and aggregate size."""
        total_size = sum(self.sim_entry_sizes)
        fallback_entry_price = (
            float(self.current_trade_record.get("entry_price"))
            if self.current_trade_record is not None and self.current_trade_record.get("entry_price") is not None
            else 0.0
        )
        fallback_anchor_price = (
            float(self.current_trade_record.get("anchor_price_at_entry"))
            if self.current_trade_record is not None and self.current_trade_record.get("anchor_price_at_entry") is not None
            else fallback_entry_price
        )
        avg_entry_price = (
            sum(price * size for price, size in zip(self.sim_entry_prices, self.sim_entry_sizes)) / total_size
            if total_size
            else fallback_entry_price
        )
        effective_anchor_price = max(self.sim_anchor_prices) if self.sim_anchor_prices else fallback_anchor_price
        return float(avg_entry_price), float(effective_anchor_price), int(total_size)

    def _compute_ladder_pnl_metrics(
        self,
        *,
        entry_price: float,
        exit_price: float,
        trade_unit: int,
        sim_num_legs: int,
        sim_avg_entry_price: float,
    ) -> dict[str, float]:
        """Return absolute PnL and incremental capital-efficiency diagnostics."""
        trade_unit = int(trade_unit or 0)
        sim_num_legs = int(sim_num_legs or 1)
        sim_total_size = trade_unit * sim_num_legs
        trade_pnl_amount = (float(exit_price) - float(entry_price)) * float(trade_unit)
        sim_trade_pnl_amount = (float(exit_price) - float(sim_avg_entry_price)) * float(sim_total_size)
        incremental_pnl_amount = sim_trade_pnl_amount - trade_pnl_amount
        incremental_notional_amount = float((sim_total_size - trade_unit) * float(entry_price))

        incremental_capital_efficiency = 0.0
        if sim_num_legs > 1 and incremental_notional_amount != 0.0:
            incremental_capital_efficiency = incremental_pnl_amount / incremental_notional_amount

        return {
            "trade_pnl_amount": float(trade_pnl_amount),
            "sim_trade_pnl_amount": float(sim_trade_pnl_amount),
            "incremental_pnl_amount": float(incremental_pnl_amount),
            "incremental_capital_efficiency": float(incremental_capital_efficiency),
        }

    def _maybe_simulate_ladder_add(
        self,
        *,
        close: float,
        current_bar: int,
        anchor_price: float,
        shock_score: float,
    ) -> None:
        """Record simulated ladder adds without sending any broker orders."""
        if (
            not self.position
            or not bool(self.p.enable_ladder_simulation)
            or self.sim_legs_count <= 0
            or self.sim_legs_count >= int(self.p.max_legs)
        ):
            return

        last_entry_price = float(self.sim_entry_prices[-1])
        min_drop_hit = float(close) <= last_entry_price * (1.0 - float(self.p.ladder_min_drop_pct))
        enough_spacing = int(current_bar) - int(self.sim_last_entry_bar) >= int(self.p.ladder_min_bars_between_legs)
        score_ok = float(shock_score) >= float(self.p.ladder_score_min_add)
        if not (min_drop_hit and enough_spacing and score_ok):
            return

        self.sim_legs_count += 1
        self.sim_entry_prices.append(float(close))
        self.sim_entry_sizes.append(int(self.p.trade_unit))
        self.sim_anchor_prices.append(float(anchor_price))
        self.sim_last_entry_bar = int(current_bar)

    def _clear_trade_state(self) -> None:
        """Reset local state after a completed trade."""
        self.current_trade_record = None
        self.current_trade_reason = None
        self.position_state = None
        self.pending_entry_context = None
        self.pending_exit_reason = None
        self._reset_ladder_state()
        self._reset_sim_ladder_state()

    def _sync_trade_metrics(self) -> None:
        """Mirror shared execution metrics onto the export record."""
        if self.current_trade_record is None or self.position_state is None:
            return
        self.current_trade_record.update(export_trade_metrics(self.position_state))

    def notify_order(self, order) -> None:
        """Capture executed entry/exit details for trade export."""
        if order.status in {order.Submitted, order.Accepted}:
            return

        if order.status in {order.Canceled, order.Margin, order.Rejected}:
            self.active_order = None
            if order.isbuy():
                self.pending_entry_context = None
            if order.issell():
                self.pending_exit_reason = None
            return

        if order.status != order.Completed:
            return

        self.active_order = None

        if order.isbuy():
            context = self.pending_entry_context or {}
            entry_price = float(order.executed.price)
            executed_size = int(order.executed.size)
            anchor_price = float(context.get("anchor_price_at_entry", entry_price))
            is_add_entry = self.current_trade_record is not None and self.position_state is not None
            if not is_add_entry:
                self.position_state = create_position_state(
                    entry_price=entry_price,
                    entry_bar=len(self),
                    anchor_price=anchor_price,
                )
                entry_exit_plan = evaluate_exit_engine(
                    close=entry_price,
                    current_bar=len(self),
                    state=self.position_state,
                    recovery_frac=self.p.recovery_frac,
                    take_profit_pct=self.p.take_profit_pct,
                    stop_loss_pct=self.p.stop_loss_pct,
                    max_hold_bars=self.p.max_hold_bars,
                )
                self.current_trade_record = {
                    "symbol": self._get_symbol(),
                    "entry_datetime": self._current_datetime(),
                    "size": executed_size,
                    "entry_price": entry_price,
                    "anchor_price_at_entry": anchor_price,
                    "excursion_at_entry": float(context.get("excursion_at_entry", 0.0)),
                    "shock_score_at_entry": float(context.get("shock_score_at_entry", 0.0)),
                    "recovery_target": entry_exit_plan.recovery_target,
                    "take_profit_price": entry_exit_plan.take_profit_price,
                    "effective_target_price": entry_exit_plan.effective_target_price,
                    **export_trade_metrics(self.position_state),
                }
                self._initialize_sim_trade_state(
                    entry_price=entry_price,
                    size=executed_size,
                    anchor_price=anchor_price,
                    current_bar=len(self),
                )
            self._record_leg(entry_price=entry_price, size=executed_size, anchor_price=anchor_price)
            self.pending_entry_context = None
            return

        if not order.issell() or self.current_trade_record is None or self.position_state is None:
            return

        exit_price = float(order.executed.price)
        update_trade_metrics(self.position_state, exit_price, len(self))
        exit_plan = evaluate_exit_engine(
            close=exit_price,
            current_bar=len(self),
            state=self.position_state,
            recovery_frac=self.p.recovery_frac,
            take_profit_pct=self.p.take_profit_pct,
            stop_loss_pct=self.p.stop_loss_pct,
            max_hold_bars=self.p.max_hold_bars,
        )
        standardized_reason = self.pending_exit_reason or self._standardize_exit_reason(exit_plan.reason)
        trade_record = dict(self.current_trade_record)
        mfe_price = float(self.position_state.mfe_price or self.position_state.entry_price)
        mae_price = float(self.position_state.mae_price or self.position_state.entry_price)
        entry_price = float(self.position_state.entry_price)
        total_entry_size = sum(self.entry_sizes)
        avg_entry_price = (
            sum(price * size for price, size in zip(self.entry_prices, self.entry_sizes)) / total_entry_size
            if total_entry_size
            else float(trade_record.get("entry_price", entry_price))
        )
        effective_anchor_price = (
            max(self.anchor_prices)
            if self.anchor_prices
            else float(trade_record.get("anchor_price_at_entry", entry_price))
        )
        sim_avg_entry_price, sim_effective_anchor_price, sim_position_size = self._compute_sim_position_metrics()
        sim_trade_return = (
            (exit_price - sim_avg_entry_price) / sim_avg_entry_price if sim_avg_entry_price else (exit_price - entry_price) / entry_price
        )
        sim_mfe = (
            (mfe_price - sim_avg_entry_price) / sim_avg_entry_price if sim_avg_entry_price else float(self.position_state.mfe_pct)
        )
        sim_mae = (
            (mae_price - sim_avg_entry_price) / sim_avg_entry_price if sim_avg_entry_price else float(self.position_state.mae_pct)
        )
        sim_etd = (
            max(0.0, (mfe_price - exit_price) / sim_avg_entry_price)
            if sim_avg_entry_price
            else max(0.0, (mfe_price - exit_price) / entry_price)
        )
        ladder_pnl_metrics = self._compute_ladder_pnl_metrics(
            entry_price=entry_price,
            exit_price=exit_price,
            trade_unit=int(trade_record.get("size", self.p.trade_unit) or self.p.trade_unit),
            sim_num_legs=int(self.sim_legs_count or 1),
            sim_avg_entry_price=sim_avg_entry_price or avg_entry_price,
        )
        trade_record.update(
            {
                "exit_datetime": self._current_datetime(),
                "exit_price": exit_price,
                "holding_bars": exit_plan.holding_bars,
                "trade_return": (exit_price - entry_price) / entry_price,
                "etd": max(0.0, (mfe_price - exit_price) / entry_price),
                "num_legs": int(self.current_legs or 1),
                "avg_entry_price": avg_entry_price,
                "effective_anchor_price": effective_anchor_price,
                "sim_num_legs": int(self.sim_legs_count or 1),
                "sim_avg_entry_price": sim_avg_entry_price or avg_entry_price,
                "sim_effective_anchor_price": sim_effective_anchor_price or effective_anchor_price,
                "sim_trade_return": sim_trade_return,
                "sim_mfe": sim_mfe,
                "sim_mae": sim_mae,
                "sim_etd": sim_etd,
                "exit_reason": standardized_reason,
                "exit_subtype": standardized_reason,
                "recovery_target": exit_plan.recovery_target,
                "take_profit_price": exit_plan.take_profit_price,
                "effective_target_price": exit_plan.effective_target_price,
                **ladder_pnl_metrics,
                **export_trade_metrics(self.position_state),
            }
        )
        self.completed_trades.append(trade_record)
        self._clear_trade_state()

    def next(self) -> None:
        self._apply_margin_interest()
        close = float(self.data.close[0])
        rolling_max_close = float(self.rolling_max_close[0])
        excursion_value = float(self.excursion[0])
        if math.isnan(excursion_value):
            return

        if len(self) < 3:
            return

        score_breakdown = compute_shock_score(
            close_now=close,
            close_prev=float(self.data.close[-1]),
            close_minus_two=float(self.data.close[-2]),
            high_now=float(self.data.high[0]),
            low_now=float(self.data.low[0]),
            excursion=excursion_value,
            excursion_threshold=float(self.p.excursion_threshold),
            close_history=[float(self.data.close[-idx]) for idx in range(min(len(self), int(self.p.noise_lookback) + 1) - 1, -1, -1)],
            speed_scale=float(self.p.speed_scale),
            noise_lookback=int(self.p.noise_lookback),
            noise_ratio_scale=float(self.p.noise_ratio_scale),
            score_weights=self.score_weights,
        )

        if self.position and self.position_state is not None:
            update_trade_metrics(self.position_state, close, len(self))
            self._sync_trade_metrics()
            self._maybe_simulate_ladder_add(
                close=close,
                current_bar=len(self),
                anchor_price=rolling_max_close,
                shock_score=score_breakdown.shock_score,
            )
            sim_avg_entry_price, sim_effective_anchor_price, sim_position_size = self._compute_sim_position_metrics()
            if self.current_trade_record is not None:
                self.current_trade_record.update(
                    {
                        "sim_num_legs": int(self.sim_legs_count or 1),
                        "sim_avg_entry_price": sim_avg_entry_price,
                        "sim_effective_anchor_price": sim_effective_anchor_price,
                        "sim_position_size": sim_position_size,
                    }
                )

        signal_trigger = excursion_value <= -self.p.excursion_threshold
        score_filter_enabled = bool(self.p.use_shock_score_filter)
        active_shock_score_min = float(self.p.shock_score_min) if score_filter_enabled else None
        active_shock_score_max = (
            None
            if not score_filter_enabled or self.p.shock_score_max is None
            else float(self.p.shock_score_max)
        )
        score_above_min = True if active_shock_score_min is None else score_breakdown.shock_score >= active_shock_score_min
        score_below_max = True if active_shock_score_max is None else score_breakdown.shock_score <= active_shock_score_max
        blocked_by_shock_score_low = bool(signal_trigger and score_filter_enabled and not score_above_min)
        blocked_by_shock_score_high = bool(signal_trigger and score_filter_enabled and not score_below_max)
        entry_signal = signal_trigger
        in_position = bool(self.position)
        exit_plan = evaluate_exit_engine(
            close=close,
            current_bar=len(self),
            state=self.position_state,
            recovery_frac=self.p.recovery_frac,
            take_profit_pct=self.p.take_profit_pct,
            stop_loss_pct=self.p.stop_loss_pct,
            max_hold_bars=self.p.max_hold_bars,
        )
        exit_reason = exit_plan.reason

        if in_position and exit_plan.signal and self.active_order is None:
            standardized_reason = self._standardize_exit_reason(exit_reason)
            self.pending_exit_reason = standardized_reason
            self.active_order = self.close()
            self.sell_events += 1
            if self.current_trade_reason is not None:
                self.trade_diagnostics.append(
                    {
                        "entry_reason": self.current_trade_reason,
                        "exit_reason": {
                            "reason": standardized_reason,
                            "exit_subtype": standardized_reason,
                            "holding_bars": exit_plan.holding_bars,
                            "recovery_target": exit_plan.recovery_target,
                            "take_profit_price": exit_plan.take_profit_price,
                            "effective_target_price": exit_plan.effective_target_price,
                            "excursion": float(excursion_value),
                        },
                    }
                )

        executed = False
        blocked_by: list[str] = []
        score_filter_enabled = bool(self.p.use_shock_score_filter)
        entry_condition = signal_trigger and not self.position and self.active_order is None
        if score_filter_enabled:
            entry_condition = entry_condition and score_above_min and score_below_max

        if entry_signal and self.position:
            blocked_by.append("in_position")
        if entry_signal and self.active_order is not None:
            blocked_by.append("active_order")
        if blocked_by_shock_score_low:
            blocked_by.append("shock_score_low")
        if blocked_by_shock_score_high:
            blocked_by.append("shock_score_high")

        if entry_condition:
            self.pending_entry_context = {
                "anchor_price_at_entry": rolling_max_close,
                "excursion_at_entry": excursion_value,
                "shock_score_at_entry": score_breakdown.shock_score,
            }
            self.active_order = self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.current_trade_reason = {
                "signal_trigger": bool(signal_trigger),
                "excursion": float(excursion_value),
                "anchor_price": float(rolling_max_close),
                "shock_score": float(score_breakdown.shock_score),
            }

        if entry_signal:
            self.signal_events.append(
                {
                    "symbol": self._get_symbol(),
                    "datetime": self._current_datetime(),
                    **score_breakdown.to_dict(),
                    "threshold": float(self.p.excursion_threshold),
                    "shock_score_min": active_shock_score_min,
                    "shock_score_max": active_shock_score_max,
                    "shock_score_filter_enabled": bool(score_filter_enabled),
                    "blocked_by_shock_score_low": bool(blocked_by_shock_score_low),
                    "blocked_by_shock_score_high": bool(blocked_by_shock_score_high),
                    "entry_executed": bool(executed),
                }
            )

        self.diagnostics.append(
            {
                "datetime": self._current_datetime(),
                "signal_trigger": bool(signal_trigger),
                **score_breakdown.to_dict(),
                "threshold": float(self.p.excursion_threshold),
                "entry_signal": bool(entry_signal),
                "shock_score_filter_enabled": bool(score_filter_enabled),
                "blocked_by_shock_score_low": bool(blocked_by_shock_score_low),
                "blocked_by_shock_score_high": bool(blocked_by_shock_score_high),
                "shock_score_pass": bool((not score_filter_enabled) or (score_above_min and score_below_max)),
                "shock_score_min": active_shock_score_min,
                "shock_score_max": active_shock_score_max,
                "executed": bool(executed),
                "blocked_by": list(blocked_by),
                "in_position": bool(self.position),
                "holding_bars": exit_plan.holding_bars if self.position_state is not None else 0,
                "recovery_target": exit_plan.recovery_target,
                "take_profit_price": exit_plan.take_profit_price,
                "effective_target_price": exit_plan.effective_target_price,
                "exit_reason": self._standardize_exit_reason(exit_reason),
            }
        )
