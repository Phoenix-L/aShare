import pandas as pd
import pytest

from ashare.data.normalizers import PandasDataWithTurnover, to_backtrader_feed


def _base_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "open": [10.0, 10.5, 11.0],
            "high": [10.2, 10.7, 11.2],
            "low": [9.8, 10.3, 10.8],
            "close": [10.1, 10.6, 11.1],
            "volume": [1000, 1200, 1500],
        },
        index=idx,
    )


def test_feed_uses_turnover_line_when_column_present() -> None:
    df = _base_df()
    df["turnover_rate"] = [1.0, 1.1, 1.2]

    feed = to_backtrader_feed(df)

    assert isinstance(feed, PandasDataWithTurnover)


def test_required_column_validation() -> None:
    df = _base_df().drop(columns=["close"])

    with pytest.raises(ValueError, match="missing column: close"):
        to_backtrader_feed(df)


def test_turnover_rate_is_optional() -> None:
    df = _base_df()

    feed = to_backtrader_feed(df)

    assert not isinstance(feed, PandasDataWithTurnover)
