import math

import pandas as pd
import pytest

from ashare.indicators.multi_day_excursion import compute_multi_day_excursion


def test_multi_day_excursion_constant_price_is_zero_after_warmup() -> None:
    df = pd.DataFrame(
        {
            "high": [10.0, 10.0, 10.0, 10.0],
            "low": [10.0, 10.0, 10.0, 10.0],
            "close": [10.0, 10.0, 10.0, 10.0],
        }
    )

    result = compute_multi_day_excursion(df, window=3)

    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.0)
    assert result.iloc[3] == pytest.approx(0.0)


def test_multi_day_excursion_increasing_price_is_positive() -> None:
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0, 12.0],
            "close": [9.5, 10.5, 11.5, 12.5],
        }
    )

    result = compute_multi_day_excursion(df, window=2)

    assert result.iloc[1] > 0
    assert result.iloc[2] > 0
    assert result.iloc[3] > 0


def test_multi_day_excursion_matches_known_values() -> None:
    df = pd.DataFrame(
        {
            "high": [10.0, 12.0, 11.0, 13.0],
            "low": [8.0, 9.0, 9.0, 10.0],
            "close": [9.0, 10.0, 10.0, 12.0],
        }
    )

    result = compute_multi_day_excursion(df, window=3)

    expected = [float("nan"), float("nan"), 0.4, 4 / 12]
    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(expected[2])
    assert result.iloc[3] == pytest.approx(expected[3])
