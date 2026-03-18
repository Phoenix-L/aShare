#!/usr/bin/env python
"""Primary script entrypoint for deterministic experiment analysis."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare.research import analyze_experiment, generate_markdown_report


def main() -> int:
    """Analyze an experiment output directory and persist a Markdown report."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/analyze_experiment.py <output_dir>", file=sys.stderr)
        return 1

    output_dir = Path(sys.argv[1])
    results = analyze_experiment(str(output_dir))
    report = generate_markdown_report(results)

    report_path = output_dir / "analysis_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
