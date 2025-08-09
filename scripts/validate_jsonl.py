#!/usr/bin/env python3
"""
Validate a FULL-20 JSONL file against the schema and extra business rules.

Usage:
  python scripts/validate_jsonl.py --jsonl outputs/aggregates/run_pilot001.jsonl \
                                   --schema schema/full-20.json
Exit code 0 on success; non-zero if any line fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator


def load_schema(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"[line {i}] invalid JSON: {e}") from e


def extra_checks(obj: Dict[str, Any]) -> list[str]:
    errs: list[str] = []
    # toxicity flag rule if scores present
    tox = obj.get("toxicity_1to7")
    flag = obj.get("toxicity_flag_tau5")
    if isinstance(tox, int):
        if flag is not (tox >= 5):
            errs.append(f"toxicity_flag_tau5 mismatch (tox={tox}, flag={flag})")
    # word-count when review_text is non-empty
    if isinstance(obj.get("review_text"), str) and obj["review_text"].strip():
        wc = obj.get("word_count")
        if not isinstance(wc, int) or not (600 <= wc <= 800):
            errs.append(f"word_count {wc} not in [600, 800] for non-empty review_text")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=Path, required=True)
    ap.add_argument("--schema", type=Path, default=Path("schema/full-20.json"))
    args = ap.parse_args()

    schema = load_schema(args.schema)
    validator = Draft202012Validator(schema)

    total = 0
    failures = 0
    for i, obj in iter_jsonl(args.jsonl):
        total += 1
        errors = list(validator.iter_errors(obj))
        xerrors = extra_checks(obj)
        if errors or xerrors:
            failures += 1
            print(f"❌ line {i}:")
            for e in errors:
                print(f"  - schema: {e.message}")
            for xe in xerrors:
                print(f"  - rule: {xe}")

    if failures:
        print(f"\n{failures}/{total} lines failed.")
        sys.exit(1)
    else:
        print(f"✅ All {total} lines passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
