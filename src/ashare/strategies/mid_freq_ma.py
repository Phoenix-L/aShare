"""Double MA crossover + turnover rate filter (mid-frequency)."""

import backtrader as bt

from ashare.constraints.ashare import calc_buy_size


class MidFreqMA(bt.Strategy):
    """Dual moving average crossover with turnover rate filter."""

    params = (
        ("short_period", 5),
        ("long_period", 20),
        ("turnover_thresh", 1.5),
    )

    def __init__(self) -> None:
        self.short_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.short_period
        )
        self.long_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.long_period
        )
        self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)

    def next(self) -> None:
        cash = self.broker.getcash()
        price = self.data.close[0]
        turnover = getattr(self.data, "turnover_rate", None)
        turnover_ok = (turnover is not None and turnover[0] > self.p.turnover_thresh) or (
            turnover is None
        )

        if not self.position and self.crossover > 0 and turnover_ok:
            size = calc_buy_size(cash, price)
            if size > 0:
                self.buy(size=size)
        elif self.position and self.crossover < 0:
            self.close()
