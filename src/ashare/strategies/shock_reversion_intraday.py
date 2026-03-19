"""Intraday shock-reversion strategy using close excursion from a rolling high."""

import math

import backtrader as bt

from ashare.strategies.components.filters import passes_trend_filter
from ashare.utils.logging import get_logger

logger = get_logger("ashare.strategies.shock_reversion_intraday")


class ShockReversionIntradayStrategy(bt.Strategy):
    """Standalone intraday shock-reversion strategy."""

    params = dict(
        trade_unit=500,
        use_trend_filter=True,
        excursion_lookback_bars=3,
        excursion_threshold=0.01,
        trend_ma_period=120,
        exit_mode="anchor_recovery",
        take_profit_pct=0.02,
        recovery_frac=0.5,
        max_hold_bars=16,
        stop_loss_pct=0.02,
    )

    def __init__(self) -> None:
        if self.p.excursion_lookback_bars is None:
            raise ValueError("Invalid config: excursion_lookback_bars required")
        if self.p.exit_mode not in {"max_hold_only", "fixed_tp", "anchor_recovery"}:
            raise ValueError("Invalid config: exit_mode must be one of max_hold_only, fixed_tp, anchor_recovery")

        daily_data = self._get_daily_ma_source()
        self.trend_ma = bt.indicators.SimpleMovingAverage(daily_data.close, period=self.p.trend_ma_period)
        self.rolling_max_close = bt.indicators.Highest(self.data.close, period=self.p.excursion_lookback_bars)
        self.excursion = (self.data.close - self.rolling_max_close) / self.rolling_max_close

        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.completed_trades: list[dict] = []
        self.current_trade_reason: dict | None = None
        self.current_trade_record: dict | None = None
        self.pending_entry_context: dict | None = None
        self.pending_exit_reason: str | None = None
        self.entry_bar: int | None = None
        self.entry_price: float | None = None
        self.active_order = None

    def _get_daily_ma_source(self):
        """Return the required daily-resampled feed used for trend calculations."""
        if len(self.datas) < 2:
            raise ValueError(
                "ShockReversionIntradayStrategy requires a daily-resampled feed at datas[1] for trend calculations."
            )

        daily_data = self.datas[1]
        timeframe = getattr(daily_data, "_timeframe", None)
        compression = getattr(daily_data, "_compression", None)
        if timeframe != bt.TimeFrame.Days or compression != 1:
            raise ValueError(
                "ShockReversionIntradayStrategy requires datas[1] to be a 1-day resampled feed for trend calculations."
            )
        return daily_data

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

    def _update_trade_excursions(self, close: float) -> None:
        """Track per-trade favorable/adverse excursion in percent."""
        if self.current_trade_record is None or self.entry_price is None or not self.position:
            return

        bars_held = 0 if self.entry_bar is None else max(0, len(self) - self.entry_bar)
        move_pct = ((close - self.entry_price) / self.entry_price) * 100.0
        if move_pct > float(self.current_trade_record["max_favorable_excursion"]):
            self.current_trade_record["max_favorable_excursion"] = move_pct
            self.current_trade_record["bars_to_mfe"] = bars_held
        if move_pct < float(self.current_trade_record["max_adverse_excursion"]):
            self.current_trade_record["max_adverse_excursion"] = move_pct
            self.current_trade_record["bars_to_mae"] = bars_held

    def _clear_trade_state(self) -> None:
        """Reset local state after a completed trade."""
        self.current_trade_record = None
        self.current_trade_reason = None
        self.pending_entry_context = None
        self.pending_exit_reason = None
        self.entry_bar = None
        self.entry_price = None

    def _resolve_exit_reason(self, close: float) -> str | None:
        """Return the first triggered exit reason for the active trade."""
        if not self.position or self.entry_price is None:
            return None

        stop_loss_hit = self.p.stop_loss_pct is not None and close <= self.entry_price * (1.0 - self.p.stop_loss_pct)
        if stop_loss_hit:
            return "stop_loss"

        if self.p.exit_mode == "fixed_tp" and self.p.take_profit_pct is not None:
            if close >= self.entry_price * (1.0 + self.p.take_profit_pct):
                return "fixed_tp"

        if self.p.exit_mode == "anchor_recovery" and self.current_trade_record is not None:
            recovery_target = self.current_trade_record.get("recovery_target")
            if recovery_target is not None and close >= float(recovery_target):
                return "anchor_recovery"

        if self.p.max_hold_bars is not None and self.entry_bar is not None:
            if (len(self) - self.entry_bar) >= self.p.max_hold_bars:
                return "max_hold"

        return None

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
            anchor_price = float(context.get("anchor_price_at_entry", order.executed.price))
            entry_price = float(order.executed.price)
            shock_depth = max(0.0, anchor_price - entry_price)
            recovery_target = entry_price + (self.p.recovery_frac * shock_depth)
            self.entry_bar = len(self)
            self.entry_price = entry_price
            self.current_trade_record = {
                "symbol": self._get_symbol(),
                "entry_datetime": self._current_datetime(),
                "entry_price": entry_price,
                "anchor_price_at_entry": anchor_price,
                "excursion_at_entry": float(context.get("excursion_at_entry", 0.0)),
                "max_favorable_excursion": 0.0,
                "max_adverse_excursion": 0.0,
                "bars_to_mfe": 0,
                "bars_to_mae": 0,
                "recovery_target": recovery_target,
            }
            self.pending_entry_context = None
            return

        if not order.issell() or self.current_trade_record is None or self.entry_price is None:
            return

        exit_price = float(order.executed.price)
        holding_bars = 0 if self.entry_bar is None else max(0, len(self) - self.entry_bar)
        trade_record = {
            key: value
            for key, value in self.current_trade_record.items()
            if key != "recovery_target"
        }
        trade_record.update(
            {
                "exit_datetime": self._current_datetime(),
                "exit_price": exit_price,
                "holding_bars": holding_bars,
                "pnl_pct": ((exit_price - self.entry_price) / self.entry_price) * 100.0,
                "exit_reason": self.pending_exit_reason or "unknown",
            }
        )
        self.completed_trades.append(trade_record)
        self._clear_trade_state()

    def next(self) -> None:
        close = float(self.data.close[0])
        trend_ma = float(self.trend_ma[-1])
        rolling_max_close = float(self.rolling_max_close[0])
        excursion_value = float(self.excursion[0])
        if math.isnan(excursion_value):
            return
        if self.p.use_trend_filter and math.isnan(trend_ma):
            return

        self._update_trade_excursions(close)

        signal_trigger = excursion_value <= -self.p.excursion_threshold
        trend_ok = passes_trend_filter(close, trend_ma, enabled=self.p.use_trend_filter)
        entry_signal = signal_trigger
        in_position = bool(self.position)
        exit_reason = self._resolve_exit_reason(close)

        if in_position and exit_reason is not None and self.active_order is None:
            self.pending_exit_reason = exit_reason
            self.active_order = self.close()
            self.sell_events += 1
            if self.current_trade_reason is not None:
                self.trade_diagnostics.append(
                    {
                        "entry_reason": self.current_trade_reason,
                        "exit_reason": {
                            "reason": exit_reason,
                            "excursion": float(excursion_value),
                        },
                    }
                )

        executed = False
        blocked_by: list[str] = []
        entry_condition = signal_trigger and trend_ok and not self.position and self.active_order is None

        if entry_signal and not self.position and not trend_ok:
            blocked_by.append("trend_filter")

        if entry_condition:
            self.pending_entry_context = {
                "anchor_price_at_entry": rolling_max_close,
                "excursion_at_entry": excursion_value,
            }
            self.active_order = self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.current_trade_reason = {
                "signal_trigger": bool(signal_trigger),
                "trend_ok": bool(trend_ok),
                "excursion": float(excursion_value),
                "anchor_price": float(rolling_max_close),
            }
            blocked_by = []

        self.diagnostics.append(
            {
                "datetime": self._current_datetime(),
                "signal_trigger": bool(signal_trigger),
                "trend_ok": bool(trend_ok),
                "excursion": float(excursion_value),
                "entry_signal": bool(entry_signal),
                "executed": bool(executed),
                "blocked_by": blocked_by,
                "in_position": bool(self.position),
                "exit_reason": exit_reason,
            }
        )
