from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator


def _load_schema(schema_path: Path) -> Dict[str, Any]:
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_full20(obj: Dict[str, Any], schema_path: Path | None = None) -> List[str]:
    """Return a list of error messages; empty list means valid."""
    if schema_path is None:
        schema_path = Path("schema/full-20.json")
    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema)

    errors: List[str] = [e.message for e in validator.iter_errors(obj)]

    # Extra rules
    tox = obj.get("toxicity_1to7")
    flag = obj.get("toxicity_flag_tau5")
    if isinstance(tox, int):
        if flag is not (tox >= 5):
            errors.append("toxicity_flag_tau5 inconsistent with toxicity_1to7")

    if isinstance(obj.get("review_text"), str) and obj["review_text"].strip():
        wc = obj.get("word_count")
        if not isinstance(wc, int) or not (600 <= wc <= 800):
            errors.append("word_count must be in [600, 800] for non-empty review_text")

    return errors
