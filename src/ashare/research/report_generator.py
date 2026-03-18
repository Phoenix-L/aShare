from __future__ import annotations

from typing import Any


def _as_percent(value: float) -> str:
    """Format a ratio as a percentage string."""
    return f"{value * 100:.2f}%"


def _as_number(value: Any) -> str:
    """Format numeric report values consistently."""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "0.0000"


def _build_insights(results: dict[str, Any]) -> list[str]:
    """Generate deterministic rule-based insights from aggregate metrics."""
    insights: list[str] = []

    trade_efficiency = float(results.get("trade_efficiency", {}).get("avg", 0.0) or 0.0)
    art_block_rate = float(results.get("filters", {}).get("blocked_by_art", 0.0) or 0.0)
    excursion_block_rate = float(results.get("filters", {}).get("blocked_by_excursion", 0.0) or 0.0)
    avg_sharpe = float(results.get("avg_sharpe", 0.0) or 0.0)

    if trade_efficiency < 0.1:
        insights.append("Strategy over-filtered: very few entry signals are converted into executed trades.")
    if art_block_rate > 0.5:
        insights.append("ART filter too restrictive: volatility gating is blocking most candidate entries.")
    if excursion_block_rate > 0.5:
        insights.append("Excursion filter limiting signals: recent displacement requirements may be too strict.")
    if avg_sharpe > 1.0:
        insights.append("Average Sharpe is healthy, suggesting the parameter sweep found broadly stable behavior.")

    if not insights:
        insights.append("No dominant failure mode detected from aggregate diagnostics; iterate using the top-ranked configurations.")

    return insights


def generate_markdown_report(results: dict[str, Any]) -> str:
    """Render a structured Markdown experiment analysis report."""
    top_configs = results.get("top_configs", []) or []
    filters = results.get("filters", {}) or {}
    trade_efficiency = results.get("trade_efficiency", {}) or {}
    insights = _build_insights(results)

    lines = [
        "# Experiment Analysis Report",
        "",
        "## Summary",
        f"- Total runs: {int(results.get('total_runs', 0) or 0)}",
        f"- Best Sharpe: {_as_number(results.get('best_sharpe', 0.0))}",
        f"- Best Return: {_as_number(results.get('best_return', 0.0))}",
        f"- Avg Sharpe: {_as_number(results.get('avg_sharpe', 0.0))}",
        f"- Avg Return: {_as_number(results.get('avg_return', 0.0))}",
        "",
        "## Top Configurations",
        "| Rank | Sharpe | Return | Params |",
        "| --- | --- | --- | --- |",
    ]

    if top_configs:
        for config in top_configs:
            lines.append(
                f"| {int(config.get('rank', 0) or 0)} | {_as_number(config.get('sharpe', 0.0))} | "
                f"{_as_number(config.get('return', 0.0))} | `{config.get('params', {})}` |"
            )
    else:
        lines.append("| - | 0.0000 | 0.0000 | `{}` |")

    lines.extend(
        [
            "",
            "## Trade Efficiency",
            f"- Avg efficiency: {_as_percent(float(trade_efficiency.get('avg', 0.0) or 0.0))}",
            "",
            "## Filter Impact",
            f"- ART block rate: {_as_percent(float(filters.get('blocked_by_art', 0.0) or 0.0))}",
            f"- Excursion block rate: {_as_percent(float(filters.get('blocked_by_excursion', 0.0) or 0.0))}",
            "",
            "## Insights",
        ]
    )
    lines.extend(f"- {insight}" for insight in insights)
    lines.extend(
        [
            "",
            "## Recommendations",
            "- Adjust `z_entry` / `z_exit` to improve signal selectivity and exit timing.",
            "- Relax ART or excursion filters if diagnostics show heavy signal suppression.",
            "- Re-run the experiment on the top-ranked configurations to confirm robustness across date ranges and symbols.",
        ]
    )

    return "\n".join(lines) + "\n"
