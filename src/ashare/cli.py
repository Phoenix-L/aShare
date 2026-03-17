"""CLI entry — backtest command and utility subcommands."""

import datetime as dt

import click

from ashare import __version__
from ashare.config.loader import load_backtest_config
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
from ashare.research.experiment_runner import run_experiment
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


@cli.command()
@click.option("--symbol", required=True, help="Stock symbol (e.g. 600519.SH)")
@click.option("--strategy", required=True, help="Strategy name (e.g. mid_freq_ma)")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--plot", is_flag=False, help="Plot backtest curve after run")
def backtest(
    symbol: str,
    strategy: str,
    start: str,
    end: str,
    plot: bool,
) -> None:
    """Run backtest for one stock, one strategy, one time range."""
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
    cerebro, strat, metrics = run_backtest(strategy_cls, df, config, symbol=symbol)

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
@click.option("--strategy", required=True, help="Strategy name (e.g. mid_freq_ma)")
@click.option("--symbols", required=True, help="Comma-separated symbols (e.g. 600519.SH,000858.SZ)")
@click.option("--param", "param_options", multiple=True, help="Parameter grid entry: key=v1,v2,v3")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def experiment(strategy: str, symbols: str, param_options: tuple[str, ...], start: str, end: str) -> None:
    """Run a multi-symbol parameter sweep experiment."""
    config = load_backtest_config()
    try:
        strategy_cls = get_strategy_class(strategy)
    except KeyError as e:
        raise click.UsageError(str(e))

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise click.UsageError("At least one symbol must be provided")

    param_grid = _parse_param_options(param_options, strategy_cls=strategy_cls)

    result = run_experiment(
        strategy_cls=strategy_cls,
        symbols=symbol_list,
        param_grid=param_grid,
        start_date=start,
        end_date=end,
        config=config,
    )

    click.echo(f"Experiment completed: {result['num_runs']} runs")
    click.echo(f"Output directory: {result['experiment_dir']}")
    click.echo(f"Results CSV: {result['results_path']}")


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
