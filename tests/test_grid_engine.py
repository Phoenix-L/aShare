from ashare.experiment.grid import deduplicate_parameter_sets, generate_parameter_sets


def test_generate_parameter_sets_returns_single_when_no_grid() -> None:
    result = generate_parameter_sets({"parameters": {"short_period": 5}, "grid": {}})
    assert result == [{"short_period": 5}]


def test_generate_parameter_sets_merges_base_with_grid_product() -> None:
    payload = {
        "parameters": {"turnover_thresh": 1.0},
        "grid": {
            "short_period": [5, 10],
            "long_period": [20, 30],
        },
    }

    result = generate_parameter_sets(payload)

    assert len(result) == 4
    assert {"turnover_thresh": 1.0, "short_period": 5, "long_period": 20} in result
    assert {"turnover_thresh": 1.0, "short_period": 10, "long_period": 30} in result


def test_excursion_deduplication() -> None:
    grid = {
        "use_multi_day_excursion": [True, False],
        "excursion_min": [0.008, 0.01],
        "excursion_window": [2, 3],
    }

    combinations = generate_parameter_sets({"parameters": {}, "grid": grid})
    final_runs = deduplicate_parameter_sets(combinations)

    assert len(final_runs) == 5
    assert {
        "use_multi_day_excursion": False,
        "excursion_min": None,
        "excursion_window": None,
    } in final_runs


def test_excursion_signal_mode_deduplicates_irrelevant_excursion_filter_and_signal_params() -> None:
    grid = {
        "signal_mode": ["zscore", "excursion"],
        "use_multi_day_excursion": [True, False],
        "excursion_min": [0.008, 0.01],
        "excursion_window": [2, 3],
        "excursion_lookback_bars": [2, 4],
        "excursion_threshold": [0.01, 0.02],
    }

    final_runs = deduplicate_parameter_sets(generate_parameter_sets({"parameters": {}, "grid": grid}))

    assert {
        "signal_mode": "zscore",
        "use_multi_day_excursion": False,
        "excursion_min": None,
        "excursion_window": None,
        "excursion_lookback_bars": None,
        "excursion_threshold": None,
    } in final_runs
    assert {
        "signal_mode": "excursion",
        "use_multi_day_excursion": True,
        "excursion_min": None,
        "excursion_window": None,
        "excursion_lookback_bars": 2,
        "excursion_threshold": 0.01,
    } in final_runs
