"""Custom broker helpers for optional unrestricted margin borrowing."""

from __future__ import annotations

from backtrader.brokers.bbroker import BackBroker


class UnrestrictedMarginBroker(BackBroker):
    """Backtrader broker with optional negative-cash support and cash charges."""

    params = (("allow_negative_cash", False),)

    def set_allow_negative_cash(self, enabled: bool) -> None:
        """Toggle whether long buys may push cash below zero."""
        self.p.allow_negative_cash = bool(enabled)
        if enabled:
            # Disable pre-submit cash rejection; real execution guard is
            # handled in the overridden `_execute`.
            self.set_checksubmit(False)

    def charge_cash(self, amount: float) -> None:
        """Immediately deduct cash/value from the broker."""
        if amount <= 0.0:
            return
        self.cash -= amount
        self._value -= amount

    def _execute(self, order, ago=None, price=None, cash=None, position=None, dtcoc=None):
        """Execute orders while optionally allowing negative cash balances."""
        if not self.p.allow_negative_cash:
            return super()._execute(order, ago=ago, price=price, cash=cash, position=position, dtcoc=dtcoc)

        if ago is not None and price is None:
            return

        if self.p.filler is None or ago is None:
            size = order.executed.remsize
        else:
            size = self.p.filler(order, price, ago)
            if not order.isbuy():
                size = -size

        comminfo = self.getcommissioninfo(order.data)

        if order.data._compensate is not None:
            data = order.data._compensate
            cinfocomp = self.getcommissioninfo(data)
        else:
            data = order.data
            cinfocomp = comminfo

        if ago is not None:
            position = self.positions[data]
            pprice_orig = position.price
            psize, pprice, opened, closed = position.pseudoupdate(size, price)
            pnl = comminfo.profitandloss(-closed, pprice_orig, price)
            cash = self.cash
        else:
            pnl = 0
            if not self.p.coo:
                price = pprice_orig = order.created.price
            else:
                if order.exectype == order.Market:
                    price = pprice_orig = order.data.open[0]
                else:
                    price = pprice_orig = order.created.price

            psize, pprice, opened, closed = position.update(size, price)

        if closed:
            if self.p.shortcash:
                closedvalue = comminfo.getvaluesize(-closed, pprice_orig)
            else:
                closedvalue = comminfo.getoperationcost(closed, pprice_orig)

            closecash = closedvalue
            if closedvalue > 0:
                closecash /= comminfo.get_leverage()

            cash += closecash + pnl * comminfo.stocklike
            closedcomm = comminfo.getcommission(closed, price)
            cash -= closedcomm

            if ago is not None:
                cash += comminfo.cashadjust(-closed, position.adjbase, price)
                self.cash = cash
        else:
            closedvalue = closedcomm = 0.0

        popened = opened
        if opened:
            if self.p.shortcash:
                openedvalue = comminfo.getvaluesize(opened, price)
            else:
                openedvalue = comminfo.getoperationcost(opened, price)

            opencash = openedvalue
            if openedvalue > 0:
                opencash /= comminfo.get_leverage()

            cash -= opencash

            openedcomm = cinfocomp.getcommission(opened, price)
            cash -= openedcomm

            if ago is not None:
                if abs(psize) > abs(opened):
                    adjsize = psize - opened
                    cash += comminfo.cashadjust(adjsize, position.adjbase, price)

                position.adjbase = price
                self.cash = cash
        else:
            openedvalue = openedcomm = 0.0

        if ago is None:
            return cash

        execsize = closed + opened

        if execsize:
            comminfo.confirmexec(execsize, price)
            position.update(execsize, price, data.datetime.datetime())

            if closed and self.p.int2pnl:
                closedcomm += self.d_credit.pop(data, 0.0)

            order.execute(
                dtcoc or data.datetime[ago],
                execsize,
                price,
                closed,
                closedvalue,
                closedcomm,
                opened,
                openedvalue,
                openedcomm,
                comminfo.margin,
                pnl,
                psize,
                pprice,
            )

            order.addcomminfo(comminfo)
            self.notify(order)
            self._ococheck(order)

        if popened and not opened:
            order.margin()
            self.notify(order)
            self._ococheck(order)
            self._bracketize(order, cancel=True)
