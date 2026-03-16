import pytest

from ashare.constraints.ashare import LOT_SIZE, calc_buy_size, round_to_lot


def test_round_to_lot_enforces_lot_size() -> None:
    assert round_to_lot(LOT_SIZE + 23) == LOT_SIZE
    assert round_to_lot(2 * LOT_SIZE) == 2 * LOT_SIZE


@pytest.mark.parametrize(
    "size,expected",
    [
        (0, 0),
        (-1, 0),
        (99, 0),
        (100, 100),
        (199.9, 100),
    ],
)
def test_round_to_lot_boundary_conditions(size: float, expected: int) -> None:
    assert round_to_lot(size) == expected


@pytest.mark.parametrize(
    "cash,price,expected",
    [
        (10_000, 10, 1000),
        (9_999, 10, 900),
        (500, 10, 0),
        (10_000, 0, 0),
        (10_000, -1, 0),
    ],
)
def test_calc_buy_size(cash: float, price: float, expected: int) -> None:
    assert calc_buy_size(cash, price) == expected


def test_calc_buy_size_respects_custom_lot_size() -> None:
    assert calc_buy_size(1000, 7, lot=10) == 140
