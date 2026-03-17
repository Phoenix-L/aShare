from ashare.experiment.grid import generate_parameter_sets


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
