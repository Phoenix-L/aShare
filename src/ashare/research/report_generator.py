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


def _sorted_group_items(grouped: dict[Any, dict[str, Any]]) -> list[tuple[Any, dict[str, Any]]]:
    """Sort grouped parameter analysis deterministically for report rendering."""
    def _sort_key(item: tuple[Any, dict[str, Any]]) -> tuple[float, str]:
        key, _ = item
        try:
            return (float(key), str(key))
        except (TypeError, ValueError):
            return (0.0, str(key))

    return sorted(grouped.items(), key=_sort_key)


def _build_parameter_analysis_insights(results: dict[str, Any]) -> list[str]:
    """Generate rule-based insights from grouped excursion parameter analysis."""
    insights: list[str] = []
    parameter_analysis = results.get("parameter_analysis", {}) or {}
    excursion_toggle = parameter_analysis.get("excursion_toggle", {}) or {}

    true_group = excursion_toggle.get(True)
    false_group = excursion_toggle.get(False)
    if true_group and false_group:
        true_sharpe = float(true_group.get("avg_sharpe", 0.0) or 0.0)
        false_sharpe = float(false_group.get("avg_sharpe", 0.0) or 0.0)
        true_return = float(true_group.get("avg_return", 0.0) or 0.0)
        false_return = float(false_group.get("avg_return", 0.0) or 0.0)

        if true_sharpe > false_sharpe and true_return >= false_return:
            insights.append("Excursion filter improves performance.")
        elif true_sharpe < false_sharpe and true_return <= false_return:
            insights.append("Excursion filter degrades performance.")
        elif abs(true_sharpe - false_sharpe) <= 0.05 and abs(true_return - false_return) <= 0.01:
            insights.append("Excursion filter currently has limited impact.")

    art_block_rate = float(results.get("filters", {}).get("blocked_by_art", 0.0) or 0.0)
    excursion_block_rate = float(results.get("filters", {}).get("blocked_by_excursion", 0.0) or 0.0)
    if art_block_rate >= max(0.10, excursion_block_rate * 2):
        insights.append("Strategy dominated by ART filtering.")

    return insights


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

    insights.extend(_build_parameter_analysis_insights(results))

    if not insights:
        insights.append("No dominant failure mode detected from aggregate diagnostics; iterate using the top-ranked configurations.")

    return insights


def _render_excursion_toggle(parameter_analysis: dict[str, Any]) -> list[str]:
    """Render ON/OFF grouped contribution analysis for the excursion filter."""
    excursion_toggle = parameter_analysis.get("excursion_toggle", {}) or {}
    true_group = excursion_toggle.get(True)
    false_group = excursion_toggle.get(False)

    lines = [
        "### 1. Excursion Filter (ON vs OFF)",
        "",
        "| Mode | Avg Sharpe | Avg Return | Runs |",
        "| --- | --- | --- | --- |",
    ]

    for label, group in (("True", true_group), ("False", false_group)):
        if group:
            lines.append(
                f"| {label} | {_as_number(group.get('avg_sharpe', 0.0))} | {_as_number(group.get('avg_return', 0.0))} | {int(group.get('num_runs', 0) or 0)} |"
            )
        else:
            lines.append(f"| {label} | 0.0000 | 0.0000 | 0 |")

    if true_group and false_group:
        true_sharpe = float(true_group.get("avg_sharpe", 0.0) or 0.0)
        false_sharpe = float(false_group.get("avg_sharpe", 0.0) or 0.0)
        true_return = float(true_group.get("avg_return", 0.0) or 0.0)
        false_return = float(false_group.get("avg_return", 0.0) or 0.0)

        if true_sharpe > false_sharpe and true_return >= false_return:
            lines.append("")
            lines.append("Auto insight: Excursion filter improves performance.")
        elif true_sharpe < false_sharpe and true_return <= false_return:
            lines.append("")
            lines.append("Auto insight: Excursion filter degrades performance.")
        else:
            lines.append("")
            lines.append("Auto insight: Excursion filter currently has mixed or limited impact.")

    return lines


def _render_sensitivity_table(title: str, grouped: dict[Any, dict[str, Any]], column_label: str) -> list[str]:
    """Render a generic grouped sensitivity table."""
    lines = [
        title,
        "",
        f"| {column_label} | Avg Sharpe | Avg Return | Runs |",
        "| --- | --- | --- | --- |",
    ]

    for group_value, group in _sorted_group_items(grouped):
        lines.append(
            f"| {group_value} | {_as_number(group.get('avg_sharpe', 0.0))} | {_as_number(group.get('avg_return', 0.0))} | {int(group.get('num_runs', 0) or 0)} |"
        )

    if len(lines) == 4:
        lines.append(f"| - | 0.0000 | 0.0000 | 0 |")

    return lines


def _render_excursion_min_insight(grouped: dict[Any, dict[str, Any]]) -> list[str]:
    """Render sensitivity insight for excursion_min."""
    if not grouped:
        return []

    best_value, best_group = max(_sorted_group_items(grouped), key=lambda item: (float(item[1].get("avg_sharpe", 0.0) or 0.0), float(item[1].get("avg_return", 0.0) or 0.0)))
    lines = ["", f"Auto insight: Best excursion_min is {best_value} based on average Sharpe {_as_number(best_group.get('avg_sharpe', 0.0))}."]

    highest_threshold = _sorted_group_items(grouped)[-1][1]
    if int(highest_threshold.get("num_runs", 0) or 0) < max(int(group.get("num_runs", 0) or 0) for group in grouped.values()):
        lines.append("Higher excursion_min values look more restrictive because they appear in fewer runs.")

    return lines


def _render_excursion_window_insight(grouped: dict[Any, dict[str, Any]]) -> list[str]:
    """Render sensitivity insight for excursion_window."""
    if not grouped:
        return []

    sorted_items = _sorted_group_items(grouped)
    smallest_window = sorted_items[0][0]
    largest_window = sorted_items[-1][0]
    return [
        "",
        f"Auto insight: Smaller windows such as {smallest_window} are more reactive, while larger windows such as {largest_window} should produce smoother excursion signals.",
    ]


def generate_markdown_report(results: dict[str, Any]) -> str:
    """Render a structured Markdown experiment analysis report."""
    top_configs = results.get("top_configs", []) or []
    filters = results.get("filters", {}) or {}
    trade_efficiency = results.get("trade_efficiency", {}) or {}
    parameter_analysis = results.get("parameter_analysis", {}) or {}
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
            "## Parameter Contribution Analysis",
            "",
        ]
    )
    lines.extend(_render_excursion_toggle(parameter_analysis))
    lines.extend(
        [
            "",
            *_render_sensitivity_table("### 2. excursion_min Sensitivity", parameter_analysis.get("excursion_min", {}) or {}, "excursion_min"),
            *_render_excursion_min_insight(parameter_analysis.get("excursion_min", {}) or {}),
            "",
            *_render_sensitivity_table("### 3. excursion_window Sensitivity", parameter_analysis.get("excursion_window", {}) or {}, "window"),
            *_render_excursion_window_insight(parameter_analysis.get("excursion_window", {}) or {}),
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
            "- Compare `use_multi_day_excursion`, `excursion_min`, and `excursion_window` groups before promoting a configuration.",
            "- Re-run the experiment on the top-ranked configurations to confirm robustness across date ranges and symbols.",
        ]
    )

    return "\n".join(lines) + "\n"
