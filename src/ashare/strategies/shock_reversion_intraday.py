"""Intraday shock-reversion strategy using close excursion from a rolling high."""

import json
import math

import pandas as pd

import backtrader as bt

from ashare.strategies.components.execution import (
    ExitDecision,
    create_position_state,
    evaluate_exit_engine,
    export_trade_metrics,
    update_trade_metrics,
)
from ashare.strategies.components.shock_score import (
    DEFAULT_SCORE_WEIGHTS,
    compute_shock_components,
    compute_weighted_score,
)
from ashare.utils.logging import get_logger

logger = get_logger("ashare.strategies.shock_reversion_intraday")


class ShockReversionIntradayStrategy(bt.Strategy):
    """Standalone intraday shock-reversion strategy."""

    uses_trend_filter = False
    uses_atr_filter = False

    params = dict(
        trade_unit=500,
        enable_ladder=False,
        ladder_min_drop_pct=0.02,
        ladder_min_bars_between_legs=1,
        add_score_min=None,
        ladder_score_min_add=0.0,
        min_bars_left_for_add=1,
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
        entry_score_weight_depth=None,
        entry_score_weight_speed=None,
        entry_score_weight_stabilization=None,
        entry_score_weight_noise_penalty=None,
        add_score_weight_depth=None,
        add_score_weight_speed=None,
        add_score_weight_stabilization=None,
        add_score_weight_noise_penalty=None,
        score_weight_depth=DEFAULT_SCORE_WEIGHTS["depth"],
        score_weight_speed=DEFAULT_SCORE_WEIGHTS["speed"],
        score_weight_stabilization=DEFAULT_SCORE_WEIGHTS["stabilization"],
        score_weight_noise_penalty=DEFAULT_SCORE_WEIGHTS["noise_penalty"],
        entry_shock_score_min=None,
        entry_shock_score_max=None,
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
        legacy_score_weights = {
            "depth": float(self.p.score_weight_depth),
            "speed": float(self.p.score_weight_speed),
            "stabilization": float(self.p.score_weight_stabilization),
            "noise_penalty": float(self.p.score_weight_noise_penalty),
        }
        self.entry_score_weights = {
            "depth": float(self.p.entry_score_weight_depth if self.p.entry_score_weight_depth is not None else legacy_score_weights["depth"]),
            "speed": float(self.p.entry_score_weight_speed if self.p.entry_score_weight_speed is not None else legacy_score_weights["speed"]),
            "stabilization": float(
                self.p.entry_score_weight_stabilization
                if self.p.entry_score_weight_stabilization is not None
                else legacy_score_weights["stabilization"]
            ),
            "noise_penalty": float(
                self.p.entry_score_weight_noise_penalty
                if self.p.entry_score_weight_noise_penalty is not None
                else legacy_score_weights["noise_penalty"]
            ),
        }
        self.add_score_weights = {
            "depth": float(self.p.add_score_weight_depth if self.p.add_score_weight_depth is not None else legacy_score_weights["depth"]),
            "speed": float(self.p.add_score_weight_speed if self.p.add_score_weight_speed is not None else legacy_score_weights["speed"]),
            "stabilization": float(
                self.p.add_score_weight_stabilization
                if self.p.add_score_weight_stabilization is not None
                else legacy_score_weights["stabilization"]
            ),
            "noise_penalty": float(
                self.p.add_score_weight_noise_penalty
                if self.p.add_score_weight_noise_penalty is not None
                else legacy_score_weights["noise_penalty"]
            ),
        }
        self.add_score_min = float(self.p.add_score_min if self.p.add_score_min is not None else self.p.ladder_score_min_add)
        (
            self.entry_score_filter_enabled,
            self.entry_shock_score_min,
            self.entry_shock_score_max,
        ) = self._resolve_entry_score_filter()

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
        self._reset_trade_state()

    def _reset_trade_state(self) -> None:
        """Reset all live trade state for the next independent position."""
        self.trade_state = {
            "is_open": False,
            "entry_bar": None,
            "bars_held": 0,
            "leg_count": 0,
            "leg_prices": [],
            "leg_sizes": [],
            "last_leg_bar": None,
            "last_leg_price": None,
            "total_size": 0,
            "avg_entry_price": None,
            "lowest_price_since_entry": None,
            "effective_anchor_price": None,
            "max_position_size": 0,
            "entry_shock_score": None,
            "add_shock_scores": [],
            "ladder_used": False,
        }

    def _validate_score_bound(self, value: float | None, label: str) -> float | None:
        """Validate one entry score bound and normalize it to float when present."""
        if value is None:
            return None
        normalized = float(value)
        if not 0.0 <= normalized <= 100.0:
            raise ValueError(f"Invalid config: {label} must be within [0, 100], got {normalized}.")
        return normalized

    def _resolve_entry_score_filter(self) -> tuple[bool, float | None, float | None]:
        """Resolve entry score filter enablement and bounds with legacy fallbacks."""
        entry_score_filter_enabled = bool(
            self.p.use_shock_score_filter
            or self.p.entry_shock_score_min is not None
            or self.p.entry_shock_score_max is not None
        )
        if not entry_score_filter_enabled:
            return False, None, None

        resolved_min = self._validate_score_bound(
            self.p.entry_shock_score_min if self.p.entry_shock_score_min is not None else self.p.shock_score_min,
            "entry_shock_score_min",
        )
        resolved_max = self._validate_score_bound(
            self.p.entry_shock_score_max if self.p.entry_shock_score_max is not None else self.p.shock_score_max,
            "entry_shock_score_max",
        )
        if resolved_min is None:
            raise ValueError(
                "Invalid config: entry score filter requires entry_shock_score_min or legacy shock_score_min."
            )
        if resolved_max is None:
            resolved_max = 100.0
        if resolved_min > resolved_max:
            raise ValueError(
                "Invalid config: entry_shock_score_min must be less than or equal to entry_shock_score_max."
            )
        return True, resolved_min, resolved_max

    def _check_entry_signal(self, entry_score: float) -> bool:
        """Return True when the current entry shock score passes the configured range filter."""
        if not self.entry_score_filter_enabled:
            return True
        return bool(self.entry_shock_score_min <= float(entry_score) <= self.entry_shock_score_max)

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
        if reason == "recovery":
            return "recovery"
        if reason == "take_profit":
            return "take_profit"
        if reason == "stop_loss":
            return "stop_loss"
        if reason == "max_hold":
            return "max_hold"
        return "unknown"

    def _sync_trade_metrics(self) -> None:
        """Mirror shared execution metrics onto the export record."""
        if self.current_trade_record is None or self.position_state is None:
            return
        self.current_trade_record.update(export_trade_metrics(self.position_state))

    def _evaluate_exit_decision(self, close: float) -> ExitDecision:
        ts = self.trade_state
        decision = evaluate_exit_engine(
            close=close,
            current_bar=len(self),
            state=self.position_state,
            entry_price=ts["avg_entry_price"],
            anchor_price=ts["effective_anchor_price"],
            lowest_price_since_entry=ts["lowest_price_since_entry"],
            holding_bars=ts["bars_held"],
            recovery_frac=self.p.recovery_frac,
            take_profit_pct=self.p.take_profit_pct,
            stop_loss_pct=self.p.stop_loss_pct,
            max_hold_bars=self.p.max_hold_bars,
        )
        if int(ts["bars_held"]) <= 0:
            return ExitDecision(
                signal=False,
                reason=None,
                holding_bars=decision.holding_bars,
                stop_loss_price=decision.stop_loss_price,
                recovery_target=decision.recovery_target,
                take_profit_price=decision.take_profit_price,
                effective_target_price=decision.effective_target_price,
            )
        return decision

    def _build_exit_snapshot(self, close: float) -> dict[str, float | int | None]:
        decision = self._evaluate_exit_decision(close)
        return {
            "holding_bars": int(decision.holding_bars),
            "stop_loss_price": decision.stop_loss_price,
            "recovery_target": decision.recovery_target,
            "take_profit_price": decision.take_profit_price,
            "effective_target_price": decision.effective_target_price,
            "close": float(close),
        }

    def _check_add_leg(self, close: float, add_shock_score: float, current_bar: int) -> bool:
        """Return True when the live trade qualifies for another real ladder leg."""
        ts = self.trade_state
        if (
            not ts["is_open"]
            or not bool(self.p.enable_ladder)
            or int(ts["leg_count"]) >= int(self.p.max_legs)
            or ts["last_leg_price"] is None
            or ts["last_leg_bar"] is None
        ):
            return False

        bars_since_last_leg = int(current_bar) - int(ts["last_leg_bar"])
        bars_left = int(self.p.max_hold_bars) - int(ts["bars_held"])
        return bool(
            float(close) <= float(ts["last_leg_price"]) * (1.0 - float(self.p.ladder_min_drop_pct))
            and bars_since_last_leg >= int(self.p.ladder_min_bars_between_legs)
            and float(add_shock_score) >= float(self.add_score_min)
            and bars_left >= int(self.p.min_bars_left_for_add)
        )

    def _check_exit_conditions(self, close: float) -> str | None:
        """Evaluate full-position liquidation conditions in strict priority order."""
        if not self.trade_state["is_open"] or self.trade_state["avg_entry_price"] is None:
            return None

        decision = self._evaluate_exit_decision(close)
        if decision.reason is None:
            return None
        return self._standardize_exit_reason(decision.reason)

    def enter_trade(self, price: float, size: int, entry_shock_score: float, add_shock_score: float) -> None:
        """Submit the initial live entry order for a new trade."""
        self.pending_entry_context = {
            "action": "entry",
            "anchor_price_at_entry": float(self.rolling_max_close[0]),
            "excursion_at_entry": float(self.excursion[0]),
            "entry_shock_score_at_signal": float(entry_shock_score),
            "add_shock_score_at_signal": float(add_shock_score),
            "shock_score_at_entry": float(entry_shock_score),
            "signal_price": float(price),
            "signal_bar": len(self),
            "size": int(size),
        }
        self.active_order = self.buy(size=size)
        self.buy_events += 1

    def add_leg(self, price: float, size: int, entry_shock_score: float, add_shock_score: float) -> None:
        """Submit one additional real ladder leg for the open trade."""
        self.pending_entry_context = {
            "action": "add",
            "anchor_price_at_entry": float(self.rolling_max_close[0]),
            "excursion_at_entry": float(self.excursion[0]),
            "entry_shock_score_at_signal": float(entry_shock_score),
            "add_shock_score_at_signal": float(add_shock_score),
            "shock_score_at_entry": float(entry_shock_score),
            "signal_price": float(price),
            "signal_bar": len(self),
            "size": int(size),
        }
        self.active_order = self.buy(size=size)
        self.buy_events += 1

    def exit_trade(self, price: float, reason: str) -> None:
        """Submit a full liquidation order for the live position."""
        self.pending_exit_reason = self._standardize_exit_reason(reason)
        if self.current_trade_record is not None:
            self.current_trade_record["pending_exit_reason"] = self.pending_exit_reason
        self.active_order = self.sell(size=int(self.trade_state["total_size"]))
        self.sell_events += 1

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
            context = dict(self.pending_entry_context or {})
            self.pending_entry_context = None
            action = context.get("action") or ("add" if self.trade_state["is_open"] else "entry")
            entry_price = float(order.executed.price)
            executed_size = int(order.executed.size)
            current_bar = len(self)
            anchor_price = float(context.get("anchor_price_at_entry", entry_price))

            if action == "entry" or not self.trade_state["is_open"]:
                self._reset_trade_state()
                self.trade_state.update(
                    {
                        "is_open": True,
                        "entry_bar": current_bar,
                        "bars_held": 0,
                        "leg_count": 1,
                        "leg_prices": [entry_price],
                        "leg_sizes": [executed_size],
                        "last_leg_bar": current_bar,
                        "last_leg_price": entry_price,
                        "total_size": executed_size,
                        "avg_entry_price": entry_price,
                        "lowest_price_since_entry": entry_price,
                        "effective_anchor_price": anchor_price,
                        "max_position_size": executed_size,
                        "entry_shock_score": float(context.get("shock_score_at_entry", 0.0)),
                        "add_shock_scores": [],
                        "ladder_used": False,
                    }
                )
                self.position_state = create_position_state(entry_price=entry_price, entry_bar=current_bar, anchor_price=anchor_price)
                entry_exit_snapshot = self._build_exit_snapshot(entry_price)
                self.current_trade_record = {
                    "symbol": self._get_symbol(),
                    "entry_datetime": self._current_datetime(),
                    "entry_bar": current_bar,
                    "position_size": executed_size,
                    "entry_price": entry_price,
                    "avg_entry_price": entry_price,
                    "anchor_price_at_entry": anchor_price,
                    "effective_anchor_price": anchor_price,
                    "excursion_at_entry": float(context.get("excursion_at_entry", 0.0)),
                    "entry_shock_score_at_entry": float(context.get("entry_shock_score_at_signal", context.get("shock_score_at_entry", 0.0))),
                    "add_shock_score_at_entry": float(context.get("add_shock_score_at_signal", 0.0)),
                    "shock_score_at_entry": float(context.get("shock_score_at_entry", 0.0)),
                    "leg_count": 1,
                    "ladder_used": False,
                    "add_shock_scores": json.dumps([]),
                    "add_score_count": 0,
                    "add_score_min": None,
                    "add_score_max": None,
                    "add_score_avg": None,
                    "max_position_size": executed_size,
                    "recovery_target": entry_exit_snapshot["recovery_target"],
                    "take_profit_price": entry_exit_snapshot["take_profit_price"],
                    "effective_target_price": entry_exit_snapshot["effective_target_price"],
                    **export_trade_metrics(self.position_state),
                }
                return

            ts = self.trade_state
            previous_total = int(ts["total_size"])
            previous_avg = float(ts["avg_entry_price"])
            new_total = previous_total + executed_size
            new_avg = ((previous_avg * previous_total) + (entry_price * executed_size)) / new_total
            ts["leg_count"] = int(ts["leg_count"]) + 1
            ts["leg_prices"].append(entry_price)
            ts["leg_sizes"].append(executed_size)
            ts["last_leg_bar"] = current_bar
            ts["last_leg_price"] = entry_price
            ts["total_size"] = new_total
            ts["avg_entry_price"] = new_avg
            ts["lowest_price_since_entry"] = min(float(ts["lowest_price_since_entry"]), entry_price)
            ts["effective_anchor_price"] = max(float(ts["effective_anchor_price"] or anchor_price), anchor_price)
            ts["max_position_size"] = max(int(ts["max_position_size"]), new_total)
            add_scores = list(ts.get("add_shock_scores", []))
            add_scores.append(float(context.get("add_shock_score_at_signal", 0.0)))
            ts["add_shock_scores"] = add_scores
            ts["ladder_used"] = True

            if self.current_trade_record is not None:
                add_exit_snapshot = self._build_exit_snapshot(entry_price)
                add_score_count = len(add_scores)
                add_score_min = min(add_scores) if add_scores else None
                add_score_max = max(add_scores) if add_scores else None
                add_score_avg = (sum(add_scores) / add_score_count) if add_scores else None
                self.current_trade_record.update(
                    {
                        "position_size": new_total,
                        "avg_entry_price": new_avg,
                        "leg_count": int(ts["leg_count"]),
                        "ladder_used": True,
                        "max_position_size": int(ts["max_position_size"]),
                        "effective_anchor_price": max(
                            float(self.current_trade_record.get("effective_anchor_price", anchor_price)),
                            anchor_price,
                        ),
                        "add_shock_scores": json.dumps(add_scores),
                        "add_score_count": add_score_count,
                        "add_score_min": add_score_min,
                        "add_score_max": add_score_max,
                        "add_score_avg": add_score_avg,
                        "recovery_target": add_exit_snapshot["recovery_target"],
                        "take_profit_price": add_exit_snapshot["take_profit_price"],
                        "effective_target_price": add_exit_snapshot["effective_target_price"],
                    }
                )
            return

        if not order.issell() or self.current_trade_record is None or self.position_state is None or not self.trade_state["is_open"]:
            return

        exit_price = float(order.executed.price)
        current_bar = len(self)
        update_trade_metrics(self.position_state, exit_price, current_bar)
        self._sync_trade_metrics()
        ts = self.trade_state
        exit_snapshot = self._build_exit_snapshot(exit_price)
        entry_bar = int(ts["entry_bar"] or current_bar)
        holding_bars = max(0, current_bar - entry_bar)
        avg_entry_price = float(ts["avg_entry_price"] or exit_price)
        total_size = int(ts["total_size"] or 0)
        mfe_price = float(self.position_state.mfe_price or self.position_state.entry_price)
        mae_price = float(self.position_state.mae_price or self.position_state.entry_price)
        trade_return = (exit_price - avg_entry_price) / avg_entry_price if avg_entry_price else 0.0
        trade_pnl_amount = (exit_price - avg_entry_price) * float(total_size)
        mfe = (mfe_price - avg_entry_price) / avg_entry_price if avg_entry_price else float(self.position_state.mfe_pct)
        mae = (mae_price - avg_entry_price) / avg_entry_price if avg_entry_price else float(self.position_state.mae_pct)
        etd = max(0.0, (mfe_price - exit_price) / avg_entry_price) if avg_entry_price else 0.0
        trade_record = dict(self.current_trade_record)
        standardized_reason = self.pending_exit_reason or trade_record.get("pending_exit_reason") or self._standardize_exit_reason(self._check_exit_conditions(exit_price))
        add_scores = [float(score) for score in self.trade_state.get("add_shock_scores", [])]
        add_score_count = len(add_scores)
        add_score_min = min(add_scores) if add_scores else None
        add_score_max = max(add_scores) if add_scores else None
        add_score_avg = (sum(add_scores) / add_score_count) if add_scores else None

        trade_record.update(
            {
                "exit_datetime": self._current_datetime(),
                "exit_bar": current_bar,
                "exit_price": exit_price,
                **export_trade_metrics(self.position_state),
                "holding_period": holding_bars,
                "holding_bars": holding_bars,
                "trade_return": trade_return,
                "trade_pnl_amount": float(trade_pnl_amount),
                "pnl_amount": float(trade_pnl_amount),
                "mfe": mfe,
                "mae": mae,
                "etd": etd,
                "leg_count": int(ts["leg_count"]),
                "avg_entry_price": avg_entry_price,
                "position_size": total_size,
                "total_size": total_size,
                "max_position_size": int(ts["max_position_size"]),
                "ladder_used": bool(ts["ladder_used"]),
                "entry_bar": entry_bar,
                "return": trade_return,
                "exit_reason": standardized_reason,
                "exit_subtype": standardized_reason,
                "add_shock_scores": json.dumps(add_scores),
                "add_score_count": add_score_count,
                "add_score_min": add_score_min,
                "add_score_max": add_score_max,
                "add_score_avg": add_score_avg,
                "recovery_target": exit_snapshot["recovery_target"],
                "take_profit_price": exit_snapshot["take_profit_price"],
                "effective_target_price": exit_snapshot["effective_target_price"],
            }
        )
        self.completed_trades.append(trade_record)
        self.current_trade_record = None
        self.current_trade_reason = None
        self.position_state = None
        self.pending_exit_reason = None
        self._reset_trade_state()

    def next(self) -> None:
        self._apply_margin_interest()
        close = float(self.data.close[0])
        low = float(self.data.low[0])
        rolling_max_close = float(self.rolling_max_close[0])
        excursion_value = float(self.excursion[0])
        if math.isnan(excursion_value):
            return

        if len(self) < 3:
            return

        score_components = compute_shock_components(
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
        )
        entry_shock_score = compute_weighted_score(score_components, self.entry_score_weights)
        add_shock_score = compute_weighted_score(score_components, self.add_score_weights)
        score_payload = {
            **score_components.to_dict(),
            "entry_shock_score": float(entry_shock_score),
            "add_shock_score": float(add_shock_score),
            "shock_score": float(entry_shock_score),
        }

        signal_trigger = excursion_value <= -self.p.excursion_threshold
        score_filter_enabled = bool(self.entry_score_filter_enabled)
        active_entry_shock_score_min = self.entry_shock_score_min if score_filter_enabled else None
        active_entry_shock_score_max = self.entry_shock_score_max if score_filter_enabled else None
        score_above_min = True if active_entry_shock_score_min is None else entry_shock_score >= active_entry_shock_score_min
        score_below_max = True if active_entry_shock_score_max is None else entry_shock_score <= active_entry_shock_score_max
        blocked_by_shock_score_low = bool(signal_trigger and score_filter_enabled and not score_above_min)
        blocked_by_shock_score_high = bool(signal_trigger and score_filter_enabled and not score_below_max)
        entry_signal = bool(signal_trigger)
        executed = False
        blocked_by: list[str] = []
        exit_reason: str | None = None
        exit_snapshot = self._build_exit_snapshot(close)

        if self.position and self.trade_state["is_open"] and self.position_state is not None:
            self.trade_state["bars_held"] = max(0, len(self) - int(self.trade_state["entry_bar"]))
            if self.trade_state["lowest_price_since_entry"] is None:
                self.trade_state["lowest_price_since_entry"] = low
            else:
                self.trade_state["lowest_price_since_entry"] = min(float(self.trade_state["lowest_price_since_entry"]), low)
            update_trade_metrics(self.position_state, close, len(self))
            self._sync_trade_metrics()
            if self.current_trade_record is not None:
                self.current_trade_record.update(
                    {
                        "avg_entry_price": float(self.trade_state["avg_entry_price"] or close),
                        "position_size": int(self.trade_state["total_size"]),
                        "leg_count": int(self.trade_state["leg_count"]),
                        "ladder_used": bool(self.trade_state["ladder_used"]),
                        "max_position_size": int(self.trade_state["max_position_size"]),
                    }
                )
            exit_reason = self._check_exit_conditions(close)
            exit_snapshot = self._build_exit_snapshot(close)
            if exit_reason is not None and self.active_order is None:
                self.exit_trade(close, exit_reason)
                if self.current_trade_reason is not None:
                    self.trade_diagnostics.append(
                        {
                            "entry_reason": self.current_trade_reason,
                            "exit_reason": {
                                "reason": self._standardize_exit_reason(exit_reason),
                                "exit_subtype": self._standardize_exit_reason(exit_reason),
                                "holding_bars": int(self.trade_state["bars_held"]),
                                "recovery_target": exit_snapshot["recovery_target"],
                                "take_profit_price": exit_snapshot["take_profit_price"],
                                "effective_target_price": exit_snapshot["effective_target_price"],
                                "excursion": float(excursion_value),
                            },
                        }
                    )
                self.diagnostics.append(
                    {
                        "datetime": self._current_datetime(),
                        "signal_trigger": bool(signal_trigger),
                        **score_payload,
                        "threshold": float(self.p.excursion_threshold),
                        "entry_signal": bool(entry_signal),
                        "shock_score_filter_enabled": bool(score_filter_enabled),
                        "blocked_by_shock_score_low": bool(blocked_by_shock_score_low),
                        "blocked_by_shock_score_high": bool(blocked_by_shock_score_high),
                        "shock_score_pass": bool((not score_filter_enabled) or (score_above_min and score_below_max)),
                        "entry_shock_score_min": active_entry_shock_score_min,
                        "entry_shock_score_max": active_entry_shock_score_max,
                        "shock_score_min": active_entry_shock_score_min,
                        "shock_score_max": active_entry_shock_score_max,
                        "add_score_min": float(self.add_score_min),
                        "executed": False,
                        "blocked_by": list(blocked_by),
                        "in_position": True,
                        "holding_bars": int(self.trade_state["bars_held"]),
                        "recovery_target": exit_snapshot["recovery_target"],
                        "take_profit_price": exit_snapshot["take_profit_price"],
                        "effective_target_price": exit_snapshot["effective_target_price"],
                        "exit_reason": self._standardize_exit_reason(exit_reason),
                    }
                )
                return
            if self.active_order is None and self._check_add_leg(close, add_shock_score, len(self)):
                self.add_leg(close, int(self.p.trade_unit), entry_shock_score, add_shock_score)
            elif signal_trigger:
                # Mirror flat-account branch: shock still firing while we cannot enter/add on this bar.
                if self.active_order is not None:
                    blocked_by.append("active_order")
                else:
                    blocked_by.append("in_position")
        else:
            entry_condition = entry_signal and not self.position and self.active_order is None
            if score_filter_enabled:
                entry_condition = entry_condition and self._check_entry_signal(entry_shock_score)
            if entry_signal and self.position:
                blocked_by.append("in_position")
            if entry_signal and self.active_order is not None:
                blocked_by.append("active_order")
            if blocked_by_shock_score_low:
                blocked_by.append("shock_score_low")
            if blocked_by_shock_score_high:
                blocked_by.append("shock_score_high")
            if entry_condition:
                self.enter_trade(close, int(self.p.trade_unit), entry_shock_score, add_shock_score)
                self.current_trade_reason = {
                    "signal_trigger": bool(signal_trigger),
                    "excursion": float(excursion_value),
                    "anchor_price": float(rolling_max_close),
                    "entry_shock_score": float(entry_shock_score),
                    "add_shock_score": float(add_shock_score),
                    "shock_score": float(entry_shock_score),
                }
                executed = True

        if entry_signal:
            self.signal_events.append(
                {
                    "symbol": self._get_symbol(),
                    "datetime": self._current_datetime(),
                    **score_payload,
                    "threshold": float(self.p.excursion_threshold),
                    "entry_shock_score_min": active_entry_shock_score_min,
                    "entry_shock_score_max": active_entry_shock_score_max,
                    "shock_score_min": active_entry_shock_score_min,
                    "shock_score_max": active_entry_shock_score_max,
                    "add_score_min": float(self.add_score_min),
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
                **score_payload,
                "threshold": float(self.p.excursion_threshold),
                "entry_signal": bool(entry_signal),
                "shock_score_filter_enabled": bool(score_filter_enabled),
                "blocked_by_shock_score_low": bool(blocked_by_shock_score_low),
                "blocked_by_shock_score_high": bool(blocked_by_shock_score_high),
                "shock_score_pass": bool((not score_filter_enabled) or (score_above_min and score_below_max)),
                "entry_shock_score_min": active_entry_shock_score_min,
                "entry_shock_score_max": active_entry_shock_score_max,
                "shock_score_min": active_entry_shock_score_min,
                "shock_score_max": active_entry_shock_score_max,
                "add_score_min": float(self.add_score_min),
                "executed": bool(executed),
                "blocked_by": list(blocked_by),
                "in_position": bool(self.position),
                "holding_bars": int(self.trade_state["bars_held"]),
                "recovery_target": exit_snapshot["recovery_target"],
                "take_profit_price": exit_snapshot["take_profit_price"],
                "effective_target_price": exit_snapshot["effective_target_price"],
                "exit_reason": self._standardize_exit_reason(exit_reason),
            }
        )
