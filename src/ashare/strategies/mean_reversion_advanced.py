"""Advanced modular mean-reversion strategy (no permanent core position)."""

import math

import backtrader as bt

from ashare.indicators import MultiDayExcursion
from ashare.strategies.components.filters import passes_art_filter, passes_trend_filter
from ashare.strategies.components.indicators import (
    build_mean_reversion_indicators,
    compute_art,
    compute_zscore,
)

ART_MIN_THRESHOLD = 0.02


class MeanReversionAdvanced(bt.Strategy):
    """Configurable mean-reversion strategy with optional trend and ART filters."""

    params = dict(
        trade_unit=500,
        z_entry=-1.5,
        z_exit=0.5,
        use_trend_filter=True,
        use_art_filter=True,
        use_multi_day_excursion=False,
        excursion_window=3,
        excursion_min=0.01,
    )

    def __init__(self) -> None:
        self.ma20, self.ma120, self.atr14 = build_mean_reversion_indicators(
            self.data,
            ma_short=20,
            ma_trend=120,
            atr_period=14,
        )
        self.excursion_ratio = MultiDayExcursion(
            self.data,
            window=self.p.excursion_window,
        ).excursion_ratio
        self.buy_events = 0
        self.sell_events = 0
        self.diagnostics: list[dict] = []
        self.trade_diagnostics: list[dict] = []
        self.current_trade_reason: dict | None = None

    def next(self) -> None:
        close = float(self.data.close[0])
        ma20 = float(self.ma20[0])
        ma120 = float(self.ma120[0])
        atr = float(self.atr14[0])
        if atr == 0:
            return

        zscore = compute_zscore(close, ma20, atr)
        art = compute_art(atr, close)
        excursion_ratio = float(self.excursion_ratio[0])

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
        art_ok = passes_art_filter(art, threshold=ART_MIN_THRESHOLD, enabled=self.p.use_art_filter)
        excursion_ready = not math.isnan(excursion_ratio)
        excursion_ok = (
            not self.p.use_multi_day_excursion
            or (excursion_ready and excursion_ratio >= self.p.excursion_min)
        )
        entry_signal = zscore <= self.p.z_entry
        executed = False
        blocked_by: list[str] = []

        if entry_signal and not self.position:
            if not trend_ok:
                blocked_by.append("trend_filter")
            if not art_ok:
                blocked_by.append("art_filter")
            if not excursion_ok:
                blocked_by.append("excursion_filter")

        entry_condition = (
            zscore <= self.p.z_entry
            and trend_ok
            and art_ok
            and excursion_ok
        )

        if not self.position and entry_condition:
            self.buy(size=self.p.trade_unit)
            self.buy_events += 1
            executed = True
            self.current_trade_reason = {
                "zscore": float(zscore),
                "trend_ok": bool(trend_ok),
                "art_ok": bool(art_ok),
                "excursion_ratio": float(excursion_ratio),
                "excursion_ok": bool(excursion_ok),
            }
            blocked_by = []

        self.diagnostics.append(
            {
                "datetime": str(self.datas[0].datetime.datetime(0)),
                "zscore": float(zscore),
                "trend_ok": bool(trend_ok),
                "art_ok": bool(art_ok),
                "excursion_ratio": float(excursion_ratio),
                "excursion_ok": bool(excursion_ok),
                "entry_signal": bool(entry_signal),
                "executed": bool(executed),
                "blocked_by": blocked_by,
            }
        )
