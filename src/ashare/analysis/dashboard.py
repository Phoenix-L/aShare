from __future__ import annotations

import argparse

from ashare.analysis.experiment_dashboard import build_experiment_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Build experiment-level dashboard CSVs")
    parser.add_argument("--experiment-path", required=True, help="Path to a completed experiment directory")
    args = parser.parse_args()
    outputs = build_experiment_dashboard(args.experiment_path)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
