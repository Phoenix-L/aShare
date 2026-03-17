"""Advanced modular mean-reversion strategy (no permanent core position)."""

import backtrader as bt

from ashare.strategies.components.filters import passes_art_filter, passes_trend_filter
from ashare.strategies.components.indicators import (
    build_mean_reversion_indicators,
    compute_art,
    compute_zscore,
)


class MeanReversionAdvanced(bt.Strategy):
    """Configurable mean-reversion strategy with optional trend and ART filters."""

    params = dict(
        trade_unit=500,
        z_entry=-1.5,
        z_exit=0.5,
        use_trend_filter=True,
        ma_period=120,
        use_art_filter=True,
        art_period=14,
        art_threshold=0.0,
        allow_ladder=False,
    )

    def __init__(self) -> None:
        self.ma20, self.ma120, self.atr14 = build_mean_reversion_indicators(
            self.data,
            ma_short=20,
            ma_trend=self.p.ma_period,
            atr_period=self.p.art_period,
        )
        self.buy_events = 0
        self.sell_events = 0

    def next(self) -> None:
        close = float(self.data.close[0])
        ma20 = float(self.ma20[0])
        ma120 = float(self.ma120[0])
        atr = float(self.atr14[0])
        if atr == 0:
            return

        zscore = compute_zscore(close, ma20, atr)
        art = compute_art(atr, close)

        if self.position and zscore >= self.p.z_exit:
            self.close()
            self.sell_events += 1
            return

        if self.position and not self.p.allow_ladder:
            return

        trend_ok = passes_trend_filter(close, ma120, enabled=self.p.use_trend_filter)
        art_ok = passes_art_filter(art, threshold=self.p.art_threshold, enabled=self.p.use_art_filter)

        if zscore <= self.p.z_entry and trend_ok and art_ok:
            self.buy(size=self.p.trade_unit)
            self.buy_events += 1
