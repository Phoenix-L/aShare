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
        """Keyword args for cerebro.broker.setcommission (and set_slippage_perc).
        
        Note: Backtrader doesn't support stamp_duty as a separate parameter.
        We combine stamp_duty with commission for simplicity (ignoring buy/sell difference).
        """
        # Combine commission and stamp_duty since Backtrader doesn't support stamp_duty separately
        # In reality, stamp_duty (0.1%) is only on sell transactions in China,
        # but for simplicity we add it to commission for both buy and sell
        combined_commission = self.commission + self.stamp_duty
        
        return {
            "commission": combined_commission,
            # "stamp_duty": self.stamp_duty,  # Commented out: Backtrader doesn't support this
        }
