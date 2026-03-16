"""Core-Satellite mean reversion strategy skeleton (Phase 1)."""

import backtrader as bt


class CoreSatelliteMeanReversion(bt.Strategy):
    """Phase 1 skeleton with indicator initialization and debug output only."""

    params = (
        ("core_size", 2000),
        ("satellite_max", 2000),
        ("ma_short", 20),
        ("ma_trend", 120),
        ("atr_period", 14),
    )

    def __init__(self) -> None:
        self.ma20 = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_short)
        self.ma120 = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_trend)
        self.atr14 = bt.indicators.ATR(self.data, period=self.p.atr_period)

    def next(self) -> None:
        close = float(self.data.close[0])
        ma20 = float(self.ma20[0])
        atr = float(self.atr14[0])
        zscore = (close - ma20) / atr if atr != 0 else 0.0

        dt = self.datas[0].datetime.date(0).isoformat()
        print(
            f"[CoreSatelliteMeanReversion] date={dt} close={close:.4f} ma20={ma20:.4f} "
            f"atr={atr:.4f} zscore={zscore:.4f}"
        )
