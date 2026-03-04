"""Capital, fees, slippage, and backtest defaults."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest engine and broker settings."""

    initial_cash: float = 100_000.0
    commission: float = 0.0003
    stamp_duty: float = 0.001
    slippage_perc: float = 0.001

    def to_broker_kwargs(self) -> dict[str, Any]:
        """Keyword args for cerebro.broker.setcommission (and set_slippage_perc)."""
        return {
            "commission": self.commission,
            "stamp_duty": self.stamp_duty,
        }
