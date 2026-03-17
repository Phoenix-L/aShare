"""Core-Satellite mean reversion strategy (Phase 2 parameterized rules)."""

import backtrader as bt


def build_mean_reversion_indicators(data, ma_short: int, ma_trend: int, atr_period: int):
    """Create and return indicators shared by mean-reversion strategies."""
    ma20 = bt.indicators.SimpleMovingAverage(data.close, period=ma_short)
    ma120 = bt.indicators.SimpleMovingAverage(data.close, period=ma_trend)
    atr14 = bt.indicators.ATR(data, period=atr_period)
    return ma20, ma120, atr14


def compute_zscore(close: float, mean_value: float, atr: float) -> float:
    """Compute mean-reversion z-score with ATR normalization."""
    return (close - mean_value) / atr


class CoreSatelliteMeanReversion(bt.Strategy):
    """Core-satellite mean reversion strategy with parameterized entry/exit rules."""

    params = dict(
        core_position=2000,
        satellite_max=2000,
        trade_unit=500,
        z_entry=[-1.5, -2.0, -2.5],
        z_exit=[0.8, 1.5],
        z_entry_mode="ladder",
        trend_filter=True,
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

        self.core_established = False
        self.orders_submitted = 0
        self.buy_events = 0
        self.sell_events = 0

    def _submit_core_if_needed(self) -> None:
        if self.core_established:
            return

        current_size = self.position.size
        if current_size >= self.p.core_position:
            self.core_established = True
            return

        to_buy = self.p.core_position - current_size
        if to_buy > 0:
            self.buy(size=to_buy)
            self.orders_submitted += 1
        self.core_established = True

    def _satellite_size(self) -> int:
        return max(0, self.position.size - self.p.core_position)

    def next(self) -> None:
        self._submit_core_if_needed()

        close = float(self.data.close[0])
        ma20 = float(self.ma20[0])
        ma120 = float(self.ma120[0])
        atr = float(self.atr14[0])
        if atr == 0:
            return

        zscore = compute_zscore(close, ma20, atr)
        satellite_size = self._satellite_size()

        allow_satellite_buy = True
        if self.p.trend_filter and close < ma120:
            allow_satellite_buy = False

        # Placeholder for future extension: support multiple z-entry styles
        # such as "ladder", "single", and "volatility_adaptive".
        # Phase 2 behavior currently assumes ladder-style entry only.
        if allow_satellite_buy:
            for threshold in self.p.z_entry:
                if zscore <= threshold and satellite_size < self.p.satellite_max:
                    buy_size = min(self.p.trade_unit, self.p.satellite_max - satellite_size)
                    if buy_size > 0:
                        self.buy(size=buy_size)
                        self.orders_submitted += 1
                        self.buy_events += 1
                        satellite_size += buy_size

        for threshold in self.p.z_exit:
            if zscore >= threshold and satellite_size > 0:
                sell_size = min(self.p.trade_unit, satellite_size)
                remaining_total = self.position.size - sell_size
                if remaining_total < self.p.core_position:
                    sell_size = max(0, self.position.size - self.p.core_position)
                if sell_size > 0:
                    self.sell(size=sell_size)
                    self.orders_submitted += 1
                    self.sell_events += 1
                    satellite_size -= sell_size
