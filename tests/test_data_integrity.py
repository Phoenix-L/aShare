import pandas as pd


def _synthetic_ohlcv() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "open": [10, 11, 12, 11, 13],
            "high": [11, 12, 13, 12, 14],
            "low": [9, 10, 11, 10, 12],
            "close": [10.5, 11.5, 12.2, 11.4, 13.0],
            "volume": [1000, 1200, 900, 1100, 1300],
        },
        index=idx,
    )


def test_timestamps_sorted() -> None:
    df = _synthetic_ohlcv()
    assert df.index.is_monotonic_increasing


def test_no_duplicate_timestamps() -> None:
    df = _synthetic_ohlcv()
    assert df.index.is_unique


def test_prices_are_positive() -> None:
    df = _synthetic_ohlcv()
    assert (df["close"] > 0).all()


def test_volume_non_negative() -> None:
    df = _synthetic_ohlcv()
    assert (df["volume"] >= 0).all()
