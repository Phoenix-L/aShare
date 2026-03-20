"""CLI entry — backtest command and utility subcommands."""

import datetime as dt
from dataclasses import replace

import click

from ashare import __version__
from ashare.config.loader import load_backtest_config
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.experiment.executor import execute_experiment_spec
from ashare.experiment.grid import generate_parameter_sets
from ashare.experiment.spec import load_experiment_spec
from ashare.research import analyze_experiment, generate_markdown_report
from ashare.research.walk_forward import run_walk_forward
from ashare.sanitytests import sanitycheck_daily, sanitycheck_minute30
from ashare.strategies import get_strategy_class
from ashare.utils.logging import get_logger, log_backtest_start, log_data_loaded, log_backtest_metrics, setup_logging

# Initialize logging when CLI module is imported (if not already initialized)
setup_logging()

logger = get_logger("ashare.cli")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="ashare")
def cli() -> None:
    """A-share algo trading research and backtesting."""
    pass



def _format_param_value(value) -> str:
    """Render ranking parameter values concisely for CLI output."""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _ranking_param_items(strategy_name: str, row: dict) -> list[tuple[str, object]]:
    """Return strategy-aware parameter items for ranked CLI output."""
    params = dict(row.get("params") or {})
    strategy_specific = {
        "mean_reversion_advanced": [("z_entry", "z_entry"), ("z_exit", "z_exit")],
        "shock_reversion_intraday": [
            ("excursion_lookback_bars", "lookback"),
            ("excursion_threshold", "excursion_threshold"),
            ("recovery_frac", "recovery_frac"),
            ("take_profit_pct", "tp"),
            ("max_hold_bars", "hold"),
            ("stop_loss_pct", "stop"),
            ("use_shock_score_filter", "use_shock_score_filter"),
            ("shock_score_min", "shock_score_min"),
        ],
    }
    if strategy_name in strategy_specific:
        return [
            (label, params[key])
            for key, label in strategy_specific[strategy_name]
            if params.get(key) is not None
        ]

    return [
        (key, value)
        for key, value in params.items()
        if value is not None
    ]


def _format_ranked_result(strategy_name: str, row: dict) -> str:
    """Format one ranked result line with strategy-aware params."""
    prefix = f"sharpe={row['sharpe']:.2f} return={row['total_return'] * 100:.2f}%"
    param_items = _ranking_param_items(strategy_name, row)
    if not param_items:
        return prefix
    rendered = " ".join(f"{label}={_format_param_value(value)}" for label, value in param_items)
    return f"{prefix} {rendered}"

def _validate_date_arg(field_name: str, value: str | None) -> str | None:
    """Validate optional CLI date arg as strict YYYY-MM-DD."""
    if value is None:
        return None

    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc

    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"{field_name} must be YYYY-MM-DD")
    return value


@cli.command()
@click.option("--symbol", required=True, help="Stock symbol (e.g. 600519.SH)")
@click.option("--strategy", required=True, help="Strategy name (e.g. mid_freq_ma)")
@click.option("--start", type=str, default=None, help="Override start date")
@click.option("--end", type=str, default=None, help="Override end date")
@click.option("--plot", is_flag=False, help="Plot backtest curve after run")
def backtest(
    symbol: str,
    strategy: str,
    start: str,
    end: str,
    plot: bool,
) -> None:
    """Run backtest for one stock, one strategy, one time range."""
    try:
        start = _validate_date_arg("start", start)
        end = _validate_date_arg("end", end)
    except ValueError as e:
        raise click.UsageError(str(e))

    config = load_backtest_config()
    try:
        strategy_cls = get_strategy_class(strategy)
    except KeyError as e:
        raise click.UsageError(str(e))

    # Log backtest start
    log_backtest_start(logger, symbol, strategy, start, end, config)

    click.echo(f"Loading 30-min data: {symbol} ({start} .. {end}) ...")
    df = load_minute_30(ts_code=symbol, start_date=start, end_date=end)
    if df.empty:
        raise click.ClickException(f"No data returned for {symbol}. Check symbol and date range.")

    # Log data loaded
    log_data_loaded(
        logger,
        symbol=symbol,
        num_bars=len(df),
        start_date=start,
        end_date=end,
        data_start=str(df.index.min()) if not df.empty else None,
        data_end=str(df.index.max()) if not df.empty else None,
    )

    click.echo(f"Initial capital: {config.initial_cash:,.2f} 元")
    cerebro, strat, metrics = run_backtest(
        strategy_cls,
        df,
        config,
        symbol=symbol,
        experiment_name="cli_backtest",
        run_id="single",
    )

    # Extract number of trades from metrics (already extracted in extract_results)
    num_trades = metrics.get("num_trades", 0)

    # Log backtest metrics
    log_backtest_metrics(logger, symbol, strategy, num_trades, metrics)

    click.echo(f"Final value: {metrics['final_value']:,.2f} 元")
    click.echo(f"Total return: {metrics['rtot'] * 100:.2f}%")
    sharpe = metrics.get("sharpe")
    click.echo(f"Sharpe ratio: {sharpe:.2f}" if sharpe is not None else "Sharpe ratio: N/A")
    click.echo(f"Max drawdown: {metrics['max_drawdown']:.2f}%")

    if plot:
        cerebro.plot()


def _coerce_scalar(value: str):
    """Coerce CLI scalar parameter to int/float/bool/str."""
    stripped = value.strip()
    if stripped == "":
        raise click.UsageError("Parameter values cannot be empty")

    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        return int(stripped)
    except ValueError:
        pass

    try:
        return float(stripped)
    except ValueError:
        return stripped


def _strategy_default_params(strategy_cls) -> dict[str, object]:
    """Return strategy default params as a dictionary."""
    defaults = strategy_cls.params
    if hasattr(defaults, "_getitems"):
        return dict(defaults._getitems())
    if isinstance(defaults, dict):
        return defaults
    if isinstance(defaults, tuple):
        return dict(defaults)
    return {}


def _parse_param_options(param_options: tuple[str, ...], strategy_cls=None) -> dict[str, list[int | float | str | bool | list]]:
    """Parse repeated --param key=v1,v2 options into param grid."""
    param_grid: dict[str, list[int | float | str | bool | list]] = {}
    defaults = _strategy_default_params(strategy_cls) if strategy_cls is not None else {}

    for option in param_options:
        if "=" not in option:
            raise click.UsageError(f"Invalid --param format: {option}. Use key=v1,v2")

        key, raw_values = option.split("=", 1)
        key = key.strip()
        if not key:
            raise click.UsageError(f"Invalid --param key in: {option}")

        values = [_coerce_scalar(v) for v in raw_values.split(",") if v.strip()]
        if not values:
            raise click.UsageError(f"No values provided for --param {key}")

        default_value = defaults.get(key)
        if isinstance(default_value, (list, tuple)):
            param_grid[key] = [values]
        else:
            param_grid[key] = values

    return param_grid


@cli.command()
@click.argument("spec_path", required=False)
@click.option("--strategy", required=False, help="Strategy name (e.g. mid_freq_ma)")
@click.option("--symbols", required=False, help="Comma-separated symbols (e.g. 600519.SH,000858.SZ)")
@click.option("--param", "param_options", multiple=True, help="Parameter grid entry: key=v1,v2,v3")
@click.option("--start", type=str, default=None, help="Override start date")
@click.option("--end", type=str, default=None, help="Override end date")
def experiment(spec_path: str | None, strategy: str | None, symbols: str | None, param_options: tuple[str, ...], start: str | None, end: str | None) -> None:
    """Run a multi-symbol parameter sweep experiment."""
    try:
        start = _validate_date_arg("start", start)
        end = _validate_date_arg("end", end)
    except ValueError as e:
        raise click.UsageError(str(e))

    config = load_backtest_config()

    if spec_path and spec_path.endswith((".yaml", ".yml")):
        spec = load_experiment_spec(spec_path)
    else:
        if not strategy:
            raise click.UsageError("--strategy is required unless a YAML experiment spec path is provided")
        if not symbols:
            raise click.UsageError("--symbols is required when not using a YAML experiment spec")
        if not start or not end:
            raise click.UsageError("--start and --end are required when not using a YAML experiment spec")

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise click.UsageError("At least one symbol must be provided")

        spec = {
            "name": f"{strategy}_cli_experiment",
            "strategy": strategy,
            "symbols": symbol_list,
            "start": start,
            "end": end,
            "parameters": {},
            "grid": {},
            "execution": {},
        }

    date_range_overridden = False

    strategy_name = spec["strategy"]
    try:
        strategy_cls = get_strategy_class(strategy_name)
    except KeyError as e:
        raise click.UsageError(str(e))

    override_grid = _parse_param_options(param_options, strategy_cls=strategy_cls)
    parameters = dict(spec.get("parameters", {}))
    grid = dict(spec.get("grid", {}))

    for key, values in override_grid.items():
        if len(values) == 1:
            parameters[key] = values[0]
            grid.pop(key, None)
        else:
            grid[key] = values
            parameters.pop(key, None)

    spec["parameters"] = parameters
    spec["grid"] = grid

    if start is not None:
        spec["start"] = start
        date_range_overridden = True
    if end is not None:
        spec["end"] = end
        date_range_overridden = True

    execution = spec.get("execution", {})
    run_config = config
    if execution:
        run_config = replace(
            config,
            initial_cash=float(execution.get("initial_cash", config.initial_cash)),
            commission=float(execution.get("commission", config.commission)),
        )

    total_runs = len(generate_parameter_sets({"strategy": strategy_name, "parameters": parameters, "grid": grid})) * len(spec["symbols"])
    click.echo(f"Running experiment: {spec['name']}")
    click.echo(f"Date range: {spec['start']} → {spec['end']} ({'CLI override' if date_range_overridden else 'from config'})")
    click.echo(f"Symbols: {', '.join(spec['symbols'])}")
    click.echo(f"Total runs: {total_runs}")

    try:
        result = execute_experiment_spec(
            strategy_cls=strategy_cls,
            strategy_name=strategy_name,
            spec=spec,
            config=run_config,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    click.echo(f"Experiment completed: {result['num_runs']} runs")
    click.echo(f"Output directory: {result['output_dir']}")
    click.echo(f"Summary CSV: {result['summary_path']}")
    click.echo(f"Sorted summary CSV: {result['summary_sorted_path']}")

    click.echo("Top 5 results:")
    for index, row in enumerate(result["results"][:5], start=1):
        click.echo(f"{index}  {_format_ranked_result(strategy_name, row)}")
    return


@cli.command(name="analyze")
@click.argument("output_dir")
def analyze(output_dir: str) -> None:
    """Analyze a completed experiment output directory and write a Markdown report."""
    from pathlib import Path

    results = analyze_experiment(output_dir)
    report = generate_markdown_report(results)
    report_path = Path(output_dir) / "analysis_report.md"
    report_path.write_text(report, encoding="utf-8")
    click.echo(str(report_path))


@cli.command(name="walk-forward")
@click.option("--symbol", required=True, help="Single symbol (e.g. 600519.SH)")
@click.option("--strategy", required=True, help="Strategy name (e.g. mid_freq_ma)")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--train-window", required=True, type=int, help="Training window size in days")
@click.option("--test-window", required=True, type=int, help="Testing window size in days")
@click.option("--param", "param_options", multiple=True, help="Parameter grid entry: key=v1,v2,v3")
def walk_forward(
    symbol: str,
    strategy: str,
    start: str,
    end: str,
    train_window: int,
    test_window: int,
    param_options: tuple[str, ...],
) -> None:
    """Run walk-forward optimization for one symbol."""
    config = load_backtest_config()
    try:
        strategy_cls = get_strategy_class(strategy)
    except KeyError as e:
        raise click.UsageError(str(e))

    param_grid = _parse_param_options(param_options, strategy_cls=strategy_cls)

    result = run_walk_forward(
        strategy_cls=strategy_cls,
        symbol=symbol,
        param_grid=param_grid,
        start_date=start,
        end_date=end,
        train_window=train_window,
        test_window=test_window,
        config=config,
    )

    click.echo(f"Walk-forward completed: {result['num_windows']} windows")
    click.echo(f"Output directory: {result['output_dir']}")
    click.echo(f"Results CSV: {result['results_path']}")


def _default_date_range(days: int = 30) -> tuple[str, str]:
    """Return (start, end) ISO dates for the last `days` days up to today."""
    today = dt.date.today()
    start = today - dt.timedelta(days=days)
    return start.isoformat(), today.isoformat()


@cli.group()
def sanitytest() -> None:
    """Sanity checks for data loaders and integrations."""
    pass


@sanitytest.command()
@click.option(
    "--symbol",
    default="000001.SZ",
    show_default=True,
    help="Stock symbol (e.g. 000001.SZ)",
)
@click.option(
    "--start",
    help="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
)
@click.option(
    "--end",
    help="End date (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Only print final PASS/FAIL.",
)
def daily(symbol: str, start: str | None, end: str | None, quiet: bool) -> None:
    """Sanity check: can we load daily OHLCV + turnover from data provider?"""
    if not start or not end:
        start, end = _default_date_range()

    result = sanitycheck_daily(ts_code=symbol, start_date=start, end_date=end)

    if quiet:
        click.echo("PASS" if result.passed else f"FAIL: {result.message}")
    else:
        click.echo("=== sanitytest: daily ===")
        click.echo(f"symbol: {symbol}, start: {start}, end: {end}")
        click.echo(result.message)
        if result.passed and result.df is not None:
            click.echo(f"\nColumns: {list(result.df.columns)}")
            click.echo("\nHead(3):")
            click.echo(result.df.head(3).to_string())

    if not result.passed:
        raise click.ClickException(result.message)


@sanitytest.command(name="minute30")
@click.option(
    "--symbol",
    default="000001.SZ",
    show_default=True,
    help="Stock symbol (e.g. 000001.SZ)",
)
@click.option(
    "--start",
    help="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
)
@click.option(
    "--end",
    help="End date (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Only print final PASS/FAIL.",
)
def minute30(symbol: str, start: str | None, end: str | None, quiet: bool) -> None:
    """Sanity check: can we load 30-min OHLCV + turnover from data provider?"""
    if not start or not end:
        start, end = _default_date_range()

    result = sanitycheck_minute30(ts_code=symbol, start_date=start, end_date=end)

    if quiet:
        click.echo("PASS" if result.passed else f"FAIL: {result.message}")
    else:
        click.echo("=== sanitytest: minute30 ===")
        click.echo(f"symbol: {symbol}, start: {start}, end: {end}")
        click.echo(result.message)
        if result.passed and result.df is not None:
            click.echo(f"\nColumns: {list(result.df.columns)}")
            click.echo("\nHead(3):")
            click.echo(result.df.head(3).to_string())

    if not result.passed:
        raise click.ClickException(result.message)
