"""Advanced z-score mean-reversion strategy (no permanent core position)."""

import math

import pandas as pd

import backtrader as bt

from ashare.strategies.components.execution import (
    create_position_state,
    export_trade_metrics,
    get_holding_bars,
    update_trade_metrics,
)
from ashare.strategies.components.filters import passes_atr_filter, passes_trend_filter
from ashare.strategies.components.indicators import compute_atr_ratio, compute_zscore
from ashare.utils.logging import get_logger

ATR_RATIO_MIN_DEFAULT = 0.02
logger = get_logger("ashare.strategies.mean_reversion_advanced")


class MeanReversionAdvanced(bt.Strategy):
    """Configurable z-score mean-reversion strategy with optional trend and ATR filters."""

    params = dict(
        trade_unit=500,
        z_entry=-1.5,
        z_exit=0.5,
        use_trend_filter=True,
        use_atr_filter=None,
        atr_ratio_min=None,
        use_art_filter=None,
        art_threshold=None,
        # Moving-average periods are interpreted as trading days and
        # are computed from a daily-resampled view of the feed.
        ma_short=20,
        ma_trend=120,
    )

    @classmethod
    def validate_data_history(cls, data_df: pd.DataFrame, params: dict | None = None) -> None:
        """Fail fast when the requested window cannot satisfy indicator warm-up."""
        defaults = cls.params
        if hasattr(defaults, "_getitems"):
            resolved = dict(defaults._getitems())
        else:
            resolved = dict(defaults)
        resolved.update(params or {})

        intraday_bars = len(data_df)
        required_intraday_bars = 14
        if intraday_bars < required_intraday_bars:
            raise ValueError(
                "MeanReversionAdvanced requires at least "
                f"{required_intraday_bars} intraday bars for ATR warm-up, got {intraday_bars}."
            )

        trading_days = int(data_df.index.normalize().nunique())
        required_trading_days = int(resolved["ma_short"])
        if trading_days < required_trading_days:
            raise ValueError(
                "MeanReversionAdvanced requires at least "
                f"{required_trading_days} trading days for ma_short warm-up, got {trading_days}."
            )

        if not bool(resolved.get("use_trend_filter", True)):
            return

        required_trend_days = int(resolved["ma_trend"])
        if trading_days < required_trend_days:
            raise ValueError(
                "MeanReversionAdvanced requires at least "
                f"{required_trend_days} trading days when use_trend_filter=True, got {trading_days}. "
                "Expand the date range or disable the trend filter."
            )

    def __init__(self) -> None:
        daily_data = self._get_daily_ma_source()
        self.ma20 = bt.indicators.SimpleMovingAverage(daily_data.close, period=self.p.ma_short)
        self.ma120 = None
        if self.p.use_trend_filter:
            self.ma120 = bt.indicators.SimpleMovingAverage(daily_data.close, period=self.p.ma_trend)
        self.atr14 = bt.indicators.ATR(self.data, period=14)
        self.atr3 = bt.indicators.ATR(self.data, period=3)
        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.current_trade_reason: dict | None = None
        self.position_state = None

        self.use_atr_filter = self._resolve_use_atr_filter()
        self.atr_ratio_min = self._resolve_atr_ratio_min()

    def _get_daily_ma_source(self):
        """Return the required daily-resampled feed used for MA calculations."""
        if len(self.datas) < 2:
            raise ValueError(
                "MeanReversionAdvanced requires a daily-resampled feed at datas[1] for MA calculations."
            )

        daily_data = self.datas[1]
        timeframe = getattr(daily_data, "_timeframe", None)
        compression = getattr(daily_data, "_compression", None)
        if timeframe != bt.TimeFrame.Days or compression != 1:
            raise ValueError(
                "MeanReversionAdvanced requires datas[1] to be a 1-day resampled feed for MA calculations."
            )
        return daily_data

    def _resolve_use_atr_filter(self) -> bool:
        """Resolve canonical vs legacy ATR filter params without breaking old configs."""
        if self.p.use_atr_filter is not None:
            if self.p.use_art_filter is not None:
                logger.warning("Warning: 'use_art_filter' is deprecated. Use 'use_atr_filter' instead.")
            return bool(self.p.use_atr_filter)

        if self.p.use_art_filter is not None:
            logger.warning("Warning: 'use_art_filter' is deprecated. Use 'use_atr_filter' instead.")
            return bool(self.p.use_art_filter)

        return True

    def _resolve_atr_ratio_min(self) -> float:
        """Resolve canonical vs legacy ATR threshold params without breaking old configs."""
        if self.p.atr_ratio_min is not None:
            if self.p.art_threshold is not None:
                logger.warning("Warning: 'art_threshold' is deprecated. Use 'atr_ratio_min' instead.")
            return float(self.p.atr_ratio_min)

        if self.p.art_threshold is not None:
            logger.warning("Warning: 'art_threshold' is deprecated. Use 'atr_ratio_min' instead.")
            return float(self.p.art_threshold)

        return ATR_RATIO_MIN_DEFAULT

    def _clear_position_state(self) -> None:
        self.position_state = None
        self.current_trade_reason = None

    def next(self) -> None:
        close = float(self.data.close[0])
        ma20 = float(self.ma20[-1])
        ma120 = float("nan") if self.ma120 is None else float(self.ma120[-1])
        atr14 = float(self.atr14[0])
        if atr14 == 0 or math.isnan(atr14) or math.isnan(ma20):
            return
        if self.p.use_trend_filter and math.isnan(ma120):
            return

        zscore = compute_zscore(close, ma20, atr14)
        atr_ratio = compute_atr_ratio(float(self.atr3[0]), close)
        signal_trigger = zscore <= self.p.z_entry
        exit_signal = zscore >= self.p.z_exit

        if self.position and self.position_state is not None:
            update_trade_metrics(self.position_state, close, len(self))

        if self.position and exit_signal:
            self.close()
            self.sell_events += 1
            if self.current_trade_reason is not None and self.position_state is not None:
                holding_bars = get_holding_bars(self.position_state, len(self))
                self.trade_diagnostics.append(
                    {
                        "entry_reason": self.current_trade_reason,
                        "exit_reason": {
                            "zscore": float(zscore),
                            "holding_bars": holding_bars,
                            "pnl_pct": ((close - self.position_state.entry_price) / self.position_state.entry_price) * 100.0,
                            **export_trade_metrics(self.position_state),
                        },
                    }
                )
            self._clear_position_state()
            return

        trend_ok = passes_trend_filter(close, ma120, enabled=self.p.use_trend_filter)
        atr_ok = passes_atr_filter(atr_ratio, threshold=self.atr_ratio_min, enabled=self.use_atr_filter)
        entry_signal = signal_trigger
        executed = False
        blocked_by: list[str] = []

        if entry_signal and not self.position:
            if not trend_ok:
                blocked_by.append("trend_filter")
            if not atr_ok:
                blocked_by.append("atr_filter")

        entry_condition = signal_trigger and trend_ok and atr_ok

        if not self.position and entry_condition:
            self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.position_state = create_position_state(entry_price=close, entry_bar=len(self))
            self.current_trade_reason = {
                "zscore": float(zscore),
                "signal_trigger": bool(signal_trigger),
                "trend_ok": bool(trend_ok),
                "atr_filter_active": bool(self.use_atr_filter),
                "atr_ok": bool(atr_ok),
                "art_ok": bool(atr_ok),
                "atr_ratio": float(atr_ratio),
            }
            blocked_by = []

        self.diagnostics.append(
            {
                "datetime": str(self.datas[0].datetime.datetime(0)),
                "zscore": float(zscore),
                "signal_trigger": bool(signal_trigger),
                "trend_ok": bool(trend_ok),
                "atr_filter_active": bool(self.use_atr_filter),
                "atr_filter_bypassed": False,
                "atr_ok": bool(atr_ok),
                "art_ok": bool(atr_ok),
                "atr_ratio": float(atr_ratio),
                "entry_signal": bool(entry_signal),
                "executed": bool(executed),
                "blocked_by": blocked_by,
                "holding_bars": None if self.position_state is None else get_holding_bars(self.position_state, len(self)),
            }
        )
