import pytest

from ashare.experiment.grid import deduplicate_parameter_sets, generate_parameter_sets


def test_generate_parameter_sets_returns_single_when_no_grid() -> None:
    result = generate_parameter_sets({"parameters": {"short_period": 5}, "grid": {}})
    assert result == [{"short_period": 5}]


def test_generate_parameter_sets_merges_base_with_grid_product() -> None:
    payload = {"parameters": {"turnover_thresh": 1.0}, "grid": {"short_period": [5, 10], "long_period": [20, 30]}}
    result = generate_parameter_sets(payload)
    assert len(result) == 4
    assert {"turnover_thresh": 1.0, "short_period": 5, "long_period": 20} in result
    assert {"turnover_thresh": 1.0, "short_period": 10, "long_period": 30} in result


def test_mean_reversion_advanced_rejects_excursion_grid_params() -> None:
    with pytest.raises(ValueError, match="does not accept excursion"):
        generate_parameter_sets({
            "strategy": "mean_reversion_advanced",
            "parameters": {"z_entry": -1.5, "z_exit": 0.5},
            "grid": {"excursion_threshold": [0.01, 0.02]},
        })


def test_shock_reversion_strategy_preserves_excursion_grid_dimensions() -> None:
    payload = {
        "strategy": "shock_reversion_intraday",
        "parameters": {},
        "grid": {
            "excursion_lookback_bars": [3, 5],
            "excursion_threshold": [0.01, 0.02],
        },
    }
    final_runs = generate_parameter_sets(payload)
    assert len(final_runs) == 4
    assert {"excursion_lookback_bars": 3, "excursion_threshold": 0.01} in final_runs
    assert {"excursion_lookback_bars": 5, "excursion_threshold": 0.02} in final_runs


def test_shock_reversion_rejects_zscore_grid_params() -> None:
    with pytest.raises(ValueError, match="does not accept z-score params"):
        generate_parameter_sets({
            "strategy": "shock_reversion_intraday",
            "parameters": {},
            "grid": {"z_entry": [-1.0, -1.5]},
        })


def test_shock_reversion_deduplicate_parameter_sets_ignores_removed_trend_params() -> None:
    combinations = [
        {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "use_trend_filter": False},
        {"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "use_trend_filter": True, "trend_ma_period": 120},
    ]
    final_runs = deduplicate_parameter_sets(combinations, strategy_name="shock_reversion_intraday")
    assert final_runs == [{"trade_unit": 500, "excursion_lookback_bars": 3, "excursion_threshold": 0.01}]


def test_shock_reversion_strategy_preserves_shock_score_max_grid_dimension() -> None:
    payload = {
        "strategy": "shock_reversion_intraday",
        "parameters": {"use_shock_score_filter": True, "shock_score_min": 60},
        "grid": {"shock_score_max": [70, 80, 90]},
    }
    final_runs = generate_parameter_sets(payload)
    assert len(final_runs) == 3
    assert {"use_shock_score_filter": True, "shock_score_min": 60, "shock_score_max": 70} in final_runs
    assert {"use_shock_score_filter": True, "shock_score_min": 60, "shock_score_max": 90} in final_runs


def test_shock_reversion_strategy_preserves_entry_score_range_grid_dimensions() -> None:
    payload = {
        "strategy": "shock_reversion_intraday",
        "parameters": {"entry_shock_score_min": 60},
        "grid": {"entry_shock_score_max": [70, 80, 90]},
    }
    final_runs = generate_parameter_sets(payload)
    assert len(final_runs) == 3
    assert {"entry_shock_score_min": 60, "entry_shock_score_max": 70} in final_runs
    assert {"entry_shock_score_min": 60, "entry_shock_score_max": 90} in final_runs
