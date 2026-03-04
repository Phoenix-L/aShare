"""A-share trading rules: lot size (100 shares per lot), etc."""

LOT_SIZE = 100


def round_to_lot(size: float, lot: int = LOT_SIZE) -> int:
    """Round share quantity down to whole lots (A-share 100 shares per lot)."""
    if size <= 0:
        return 0
    return int(size // lot) * lot


def calc_buy_size(cash: float, price: float, lot: int = LOT_SIZE) -> int:
    """Max number of shares buyable with given cash, in whole lots."""
    if price <= 0:
        return 0
    return round_to_lot(cash / price, lot)
