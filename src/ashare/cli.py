"""CLI entry — backtest command and utility subcommands."""

import datetime as dt

import click

from ashare import __version__
from ashare.config.loader import load_backtest_config
from ashare.data.loaders import load_minute_30
from ashare.engine.runner import run_backtest
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
