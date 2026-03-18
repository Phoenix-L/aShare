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
