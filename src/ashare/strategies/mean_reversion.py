"""Satellite-only mean reversion strategy."""

import backtrader as bt

from ashare.strategies.components.indicators import (
    build_mean_reversion_indicators,
    compute_zscore,
)


class MeanReversion(bt.Strategy):
    """Pure mean-reversion strategy without a permanent core position."""

    params = dict(
        trade_unit=500,
        z_entry=-1.5,
        z_exit=1.0,
        allow_ladder=False,
        ma_short=20,
        ma_trend=120,
        atr_period=14,
    )

    def __init__(self) -> None:
        self.ma20, self.ma120, self.atr14 = build_mean_reversion_indicators(
            self.data,
            ma_short=self.p.ma_short,
            ma_trend=self.p.ma_trend,
            atr_period=self.p.atr_period,
        )
        self.buy_events = 0
        self.sell_events = 0

    def next(self) -> None:
        atr = float(self.atr14[0])
        if atr == 0:
            return

        close = float(self.data.close[0])
        ma20 = float(self.ma20[0])
        zscore = compute_zscore(close, ma20, atr)

        if not self.position:
            if zscore <= self.p.z_entry:
                self.buy(size=self.p.trade_unit)
                self.buy_events += 1
            return

        if zscore >= self.p.z_exit:
            self.close()
            self.sell_events += 1
