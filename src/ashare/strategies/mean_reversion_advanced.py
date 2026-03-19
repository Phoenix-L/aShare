"""Advanced modular mean-reversion strategy (no permanent core position)."""

import math

import backtrader as bt

from ashare.indicators import MultiDayExcursion
from ashare.strategies.components.filters import passes_atr_filter, passes_trend_filter
from ashare.strategies.components.indicators import (
    build_mean_reversion_indicators,
    compute_atr_ratio,
    compute_zscore,
)
from ashare.utils.logging import get_logger

ATR_RATIO_MIN_DEFAULT = 0.02
logger = get_logger("ashare.strategies.mean_reversion_advanced")


class MeanReversionAdvanced(bt.Strategy):
    """Configurable mean-reversion strategy with optional trend and ATR filters."""

    params = dict(
        trade_unit=500,
        z_entry=-1.5,
        z_exit=0.5,
        use_trend_filter=True,
        use_atr_filter=None,
        atr_ratio_min=None,
        use_art_filter=None,
        art_threshold=None,
        use_multi_day_excursion=False,
        # Moving-average periods are interpreted as trading days and
        # are computed from a daily-resampled view of the feed.
        ma_short=20,
        ma_trend=120,
        excursion_window=3,
        excursion_min=0.01,
    )

    def __init__(self) -> None:
        if self.p.use_multi_day_excursion and self.p.excursion_window is None:
            raise ValueError("Invalid config: excursion_window required")

        daily_data = self._get_daily_ma_source()
        self.ma20, self.ma120, self.atr14 = build_mean_reversion_indicators(
            self.data,
            ma_short=self.p.ma_short,
            ma_trend=self.p.ma_trend,
            atr_period=14,
            ma_source=daily_data,
            atr_source=self.data,  # keep ATR on intraday data
        )
        # Use a shorter ATR for ATR/price volatility filter (atr_ratio) only.
        self.atr3 = bt.indicators.ATR(self.data, period=3)

        if self.p.use_multi_day_excursion:
            self.excursion_ratio = MultiDayExcursion(
                self.data,
                window=self.p.excursion_window,
            ).excursion_ratio
        else:
            self.excursion_ratio = None
        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.current_trade_reason: dict | None = None

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

    def next(self) -> None:
        close = float(self.data.close[0])
        # Use previous completed daily bar for MA-based decisions.
        ma20 = float(self.ma20[-1])
        ma120 = float(self.ma120[-1])
        atr14 = float(self.atr14[0])
        # MA20 is always required for z-score. MA120 is only required when
        # the trend filter is enabled.
        if atr14 == 0 or math.isnan(atr14) or math.isnan(ma20):
            return
        if self.p.use_trend_filter and math.isnan(ma120):
            return

        zscore = compute_zscore(close, ma20, atr14)
        atr_ratio = compute_atr_ratio(float(self.atr3[0]), close)

        if self.p.use_multi_day_excursion:
            excursion_ratio = float(self.excursion_ratio[0])
            excursion_ready = not math.isnan(excursion_ratio)
            excursion_ok = excursion_ready and excursion_ratio >= self.p.excursion_min
        else:
            excursion_ratio = None
            excursion_ok = True

        if self.position and zscore >= self.p.z_exit:
            self.close()
            self.sell_events += 1
            if self.current_trade_reason is not None:
                self.trade_diagnostics.append(
                    {
                        "entry_reason": self.current_trade_reason,
                        "exit_reason": {
                            "zscore": float(zscore),
                        },
                    }
                )
                self.current_trade_reason = None
            return

        trend_ok = passes_trend_filter(close, ma120, enabled=self.p.use_trend_filter)
        atr_ok = passes_atr_filter(atr_ratio, threshold=self.atr_ratio_min, enabled=self.use_atr_filter)
        entry_signal = zscore <= self.p.z_entry
        executed = False
        blocked_by: list[str] = []

        if entry_signal and not self.position:
            if not trend_ok:
                blocked_by.append("trend_filter")
            if not atr_ok:
                blocked_by.append("atr_filter")
            if self.p.use_multi_day_excursion and not excursion_ok:
                blocked_by.append("excursion_filter")

        entry_condition = (
            zscore <= self.p.z_entry
            and trend_ok
            and atr_ok
            and excursion_ok
        )

        if not self.position and entry_condition:
            self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.current_trade_reason = {
                "zscore": float(zscore),
                "trend_ok": bool(trend_ok),
                "atr_ok": bool(atr_ok),
                "art_ok": bool(atr_ok),
                "atr_ratio": float(atr_ratio),
                "excursion_ratio": excursion_ratio,
                "excursion_ok": bool(excursion_ok),
            }
            blocked_by = []

        self.diagnostics.append(
            {
                "datetime": str(self.datas[0].datetime.datetime(0)),
                "zscore": float(zscore),
                "trend_ok": bool(trend_ok),
                "atr_ok": bool(atr_ok),
                "art_ok": bool(atr_ok),
                "atr_ratio": float(atr_ratio),
                "excursion_ratio": excursion_ratio,
                "excursion_ok": bool(excursion_ok),
                "entry_signal": bool(entry_signal),
                "executed": bool(executed),
                "blocked_by": blocked_by,
            }
        )
