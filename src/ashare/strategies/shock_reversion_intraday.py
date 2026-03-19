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
        max_hold_bars=16,
        stop_loss_pct=0.02,
    )

    def __init__(self) -> None:
        if self.p.excursion_lookback_bars is None:
            raise ValueError("Invalid config: excursion_lookback_bars required")

        daily_data = self._get_daily_ma_source()
        self.trend_ma = bt.indicators.SimpleMovingAverage(daily_data.close, period=self.p.trend_ma_period)
        rolling_max_close = bt.indicators.Highest(self.data.close, period=self.p.excursion_lookback_bars)
        self.excursion = (self.data.close - rolling_max_close) / rolling_max_close

        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.completed_trades: list[dict] = []
        self.current_trade_reason: dict | None = None
        self.current_trade_record: dict | None = None
        self.pending_exit_reason: str | None = None
        self.entry_bar: int | None = None
        self.entry_price: float | None = None

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

        move_pct = ((close - self.entry_price) / self.entry_price) * 100.0
        self.current_trade_record["max_favorable_excursion"] = max(
            float(self.current_trade_record["max_favorable_excursion"]),
            move_pct,
        )
        self.current_trade_record["max_adverse_excursion"] = min(
            float(self.current_trade_record["max_adverse_excursion"]),
            move_pct,
        )

    def notify_order(self, order) -> None:
        """Capture executed entry/exit details for trade export."""
        if order.status != order.Completed:
            return

        if order.isbuy():
            self.entry_bar = len(self)
            self.entry_price = float(order.executed.price)
            self.current_trade_record = {
                "symbol": self._get_symbol(),
                "entry_datetime": self._current_datetime(),
                "entry_price": float(order.executed.price),
                "max_favorable_excursion": 0.0,
                "max_adverse_excursion": 0.0,
            }
            return

        if not order.issell() or self.current_trade_record is None or self.entry_price is None:
            return

        exit_price = float(order.executed.price)
        holding_bars = 0 if self.entry_bar is None else max(0, len(self) - self.entry_bar)
        trade_record = {
            **self.current_trade_record,
            "exit_datetime": self._current_datetime(),
            "exit_price": exit_price,
            "holding_bars": holding_bars,
            "pnl_pct": ((exit_price - self.entry_price) / self.entry_price) * 100.0,
            "exit_reason": self.pending_exit_reason or "unknown",
        }
        self.completed_trades.append(trade_record)
        self.current_trade_record = None
        self.current_trade_reason = None
        self.pending_exit_reason = None
        self.entry_bar = None
        self.entry_price = None

    def next(self) -> None:
        close = float(self.data.close[0])
        trend_ma = float(self.trend_ma[-1])
        excursion_value = float(self.excursion[0])
        if math.isnan(excursion_value):
            return
        if self.p.use_trend_filter and math.isnan(trend_ma):
            return

        self._update_trade_excursions(close)

        signal_trigger = excursion_value <= -self.p.excursion_threshold
        trend_ok = passes_trend_filter(close, trend_ma, enabled=self.p.use_trend_filter)
        in_position = bool(self.position)

        max_hold_hit = False
        if in_position and self.entry_bar is not None and self.p.max_hold_bars is not None:
            max_hold_hit = (len(self) - self.entry_bar) >= self.p.max_hold_bars

        stop_loss_hit = False
        if in_position and self.entry_price is not None and self.p.stop_loss_pct is not None:
            stop_loss_hit = close <= self.entry_price * (1.0 - self.p.stop_loss_pct)

        if in_position and (max_hold_hit or stop_loss_hit):
            self.pending_exit_reason = "max_hold" if max_hold_hit else "stop_loss"
            self.close()
            self.sell_events += 1
            if self.current_trade_reason is not None:
                self.trade_diagnostics.append(
                    {
                        "entry_reason": self.current_trade_reason,
                        "exit_reason": {
                            "reason": self.pending_exit_reason,
                            "max_hold_hit": bool(max_hold_hit),
                            "stop_loss_hit": bool(stop_loss_hit),
                            "excursion": float(excursion_value),
                        },
                    }
                )

        executed = False
        blocked_by: list[str] = []
        entry_signal = signal_trigger
        entry_condition = signal_trigger and trend_ok and not self.position

        if entry_signal and not self.position and not trend_ok:
            blocked_by.append("trend_filter")

        if entry_condition:
            self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.current_trade_reason = {
                "signal_trigger": bool(signal_trigger),
                "trend_ok": bool(trend_ok),
                "excursion": float(excursion_value),
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
                "max_hold_hit": bool(max_hold_hit),
                "stop_loss_hit": bool(stop_loss_hit),
            }
        )
