#!/usr/bin/env python3
"""Create a new research note from the shock_reversion_intraday template."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "research" / "shock_reversion_intraday"
TEMPLATE_PATH = BASE_DIR / "notebook" / "TEMPLATE.md"
NOTEBOOK_DIR = BASE_DIR / "notebook"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "note"


def create_note(title: str) -> Path:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{slugify(title)}.md"
    note_path = NOTEBOOK_DIR / filename

    shutil.copyfile(TEMPLATE_PATH, note_path)
    return note_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new shock_reversion_intraday research note."
    )
    parser.add_argument(
        "title",
        help="Short note title used in the generated filename.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    note_path = create_note(args.title)
    print(note_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
