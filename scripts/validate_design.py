#!/usr/bin/env python3
"""Validate the repository design contract against its committed schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "docs" / "vision.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (root / "schemas" / "repo-vision-contract.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(contract), key=lambda item: list(item.path)
    )
    if errors:
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"{location}: {error.message}")
        return 1
    print("design contract: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
