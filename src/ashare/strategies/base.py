"""Base strategy / params interface (optional common base for all strategies)."""

import backtrader as bt

from ashare.utils.logging import get_logger, log_buy_order, log_sell_order


class BaseStrategy(bt.Strategy):
    """Base class for ashare strategies with transaction logging."""

    def __init__(self) -> None:
        """Initialize strategy with logging."""
        super().__init__()
        self.logger = get_logger(f"ashare.strategies.{self.__class__.__name__}")
        self._last_buy_price: dict[str, float] = {}  # Track buy prices for PnL calculation
        self._last_order_reason: str | None = None  # Track reason for last order
        self._symbol: str | None = None  # Cache symbol name

    def _get_symbol(self, data) -> str:
        """Extract symbol name from data feed."""
        if self._symbol:
            return self._symbol
        
        # Try various ways to get symbol name
        # Backtrader stores name in data._name or data.p.name
        if hasattr(data, '_name') and data._name:
            self._symbol = data._name
        elif hasattr(data, 'p') and hasattr(data.p, 'name') and data.p.name:
            self._symbol = data.p.name
        elif hasattr(data, 'p') and hasattr(data.p, 'dataname'):
            # Try to get from dataname if it's a string
            dataname = data.p.dataname
            if isinstance(dataname, str):
                self._symbol = dataname
            elif hasattr(dataname, 'name'):
                self._symbol = dataname.name
        else:
            self._symbol = 'UNKNOWN'
        
        return self._symbol

    def notify_order(self, order) -> None:
        """Called when order status changes. Logs order execution."""
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted but not executed yet
            return

        symbol = self._get_symbol(order.data)

        if order.status in [order.Completed]:
            # Order executed
            # Get datetime - try multiple methods
            try:
                dt = self.data.datetime.datetime(0)
                dt_str = dt.isoformat()
            except (AttributeError, TypeError):
                try:
                    dt_str = str(self.data.datetime.date(0))
                except (AttributeError, TypeError):
                    dt_str = str(self.data.datetime[0])

            if order.isbuy():
                # Buy order executed
                cash_before = self.broker.getcash() + order.executed.value
                cash_after = self.broker.getcash()
                
                log_buy_order(
                    self.logger,
                    symbol=symbol,
                    strategy=self.__class__.__name__,
                    datetime=dt_str,
                    price=order.executed.price,
                    size=order.executed.size,
                    value=order.executed.value,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    reason=self._last_order_reason,
                )
                
                # Store buy price for PnL calculation
                self._last_buy_price[symbol] = order.executed.price
                # Clear reason after logging
                self._last_order_reason = None

            elif order.issell():
                # Sell order executed
                cash_before = self.broker.getcash() - order.executed.value
                cash_after = self.broker.getcash()
                
                # Calculate PnL if we have buy price
                buy_price = self._last_buy_price.get(symbol, None)
                pnl = None
                pnl_pct = None
                
                if buy_price is not None:
                    pnl = (order.executed.price - buy_price) * order.executed.size
                    pnl_pct = ((order.executed.price - buy_price) / buy_price) * 100
                    # Remove buy price after sell
                    del self._last_buy_price[symbol]
                
                log_sell_order(
                    self.logger,
                    symbol=symbol,
                    strategy=self.__class__.__name__,
                    datetime=dt_str,
                    price=order.executed.price,
                    size=order.executed.size,
                    value=order.executed.value,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=self._last_order_reason,
                )
                # Clear reason after logging
                self._last_order_reason = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # Order canceled, margin call, or rejected
            self.logger.warning(
                f"order_failed symbol={symbol} status={order.getstatusname()} "
                f"size={order.size} isbuy={order.isbuy()}"
            )

    def notify_trade(self, trade) -> None:
        """Called when trade is closed. Logs trade completion with final PnL."""
        if trade.isclosed:
            symbol = self._get_symbol(trade.data)
            
            # Get datetime
            try:
                dt = self.data.datetime.datetime(0)
                dt_str = dt.isoformat()
            except (AttributeError, TypeError):
                try:
                    dt_str = str(self.data.datetime.date(0))
                except (AttributeError, TypeError):
                    dt_str = str(self.data.datetime[0])
            
            self.logger.debug(
                f"trade_closed symbol={symbol} datetime={dt_str} "
                f"pnl={trade.pnl:.2f} pnlcomm={trade.pnlcomm:.2f} barlen={trade.barlen}"
            )
