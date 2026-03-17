"""Minimal YAML compatibility layer for environments without PyYAML.

Supports a safe subset used by this project: mappings, lists, scalars,
and inline lists (e.g. [1, 2]).
"""

from __future__ import annotations

import ast
from typing import Any


class _Line:
    def __init__(self, raw: str) -> None:
        self.indent = len(raw) - len(raw.lstrip(" "))
        self.text = raw.strip()


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None

    if value.startswith("[") and value.endswith("]"):
        normalized = value.replace("true", "True").replace("false", "False").replace("null", "None")
        return ast.literal_eval(normalized)

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def safe_load(content: str) -> Any:
    lines = []
    for raw in content.splitlines():
        cleaned = raw.split("#", 1)[0].rstrip()
        if cleaned.strip():
            lines.append(_Line(cleaned))

    if not lines:
        return None

    idx = 0

    def parse_block(expected_indent: int):
        nonlocal idx
        if idx >= len(lines):
            return {}

        if lines[idx].text.startswith("- "):
            items = []
            while idx < len(lines) and lines[idx].indent == expected_indent and lines[idx].text.startswith("- "):
                item_text = lines[idx].text[2:].strip()
                idx += 1
                if not item_text:
                    items.append(parse_block(expected_indent + 2))
                elif idx < len(lines) and lines[idx].indent > expected_indent:
                    if ":" in item_text:
                        key, val = item_text.split(":", 1)
                        obj = {key.strip(): _parse_scalar(val.strip()) if val.strip() else parse_block(expected_indent + 2)}
                        nested = parse_block(expected_indent + 2)
                        if isinstance(nested, dict):
                            obj.update(nested)
                        items.append(obj)
                    else:
                        items.append(_parse_scalar(item_text))
                        _ = parse_block(expected_indent + 2)
                else:
                    items.append(_parse_scalar(item_text))
            return items

        mapping = {}
        while idx < len(lines) and lines[idx].indent == expected_indent and not lines[idx].text.startswith("- "):
            text = lines[idx].text
            if ":" not in text:
                raise ValueError(f"Invalid YAML line: {text}")
            key, val = text.split(":", 1)
            key = key.strip()
            val = val.strip()
            idx += 1
            if val:
                mapping[key] = _parse_scalar(val)
            else:
                if idx < len(lines) and lines[idx].indent > expected_indent:
                    mapping[key] = parse_block(expected_indent + 2)
                else:
                    mapping[key] = {}
        return mapping

    return parse_block(lines[0].indent)


def _dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    return repr(value)


def safe_dump(data: Any, sort_keys: bool = False) -> str:
    def dump_obj(obj: Any, indent: int) -> list[str]:
        prefix = " " * indent
        if isinstance(obj, dict):
            keys = sorted(obj.keys()) if sort_keys else obj.keys()
            out: list[str] = []
            for key in keys:
                value = obj[key]
                if isinstance(value, (dict, list)):
                    out.append(f"{prefix}{key}:")
                    out.extend(dump_obj(value, indent + 2))
                else:
                    out.append(f"{prefix}{key}: {_dump_scalar(value)}")
            return out

        if isinstance(obj, list):
            out = []
            for value in obj:
                if isinstance(value, (dict, list)):
                    out.append(f"{prefix}-")
                    out.extend(dump_obj(value, indent + 2))
                else:
                    out.append(f"{prefix}- {_dump_scalar(value)}")
            return out

        return [f"{prefix}{_dump_scalar(obj)}"]

    return "\n".join(dump_obj(data, 0)) + "\n"
