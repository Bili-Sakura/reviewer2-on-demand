from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path("schema/full-20.json")


def load_schema():
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_stub_line_validates_without_review_text(tmp_path):
    schema = load_schema()
    v = Draft202012Validator(schema)

    obj = {
        "paper_id": "ml_3f9a2c7b",
        "paper_title": "Gaussian Widgets",
        "arm": "harsh",
        "model": "gpt-5",
        "decoding": {"temperature": 0, "top_p": 1},
        "persona_version": "A",
        "content_scope": "FULL+FIG",
        "review_text": "",
        "word_count": 0,
        "helpfulness_1to7": None,
        "toxicity_1to7": None,
        "harshness_1to7": None,
        "run_id": "pilot001",
        "timestamp_iso": "2025-08-09T13:00:00+09:00",
        "source_type": "your-library",
        "paper_url": "https://example.org/paper.pdf",
        "fig_mode": "VISION",
        "judge_model": "Claude",
        "toxicity_flag_tau5": False,
        "notes": ""
    }
    errs = list(v.iter_errors(obj))
    assert not errs, f"schema errors: {[e.message for e in errs]}"


def test_filled_line_requires_600_to_800_words():
    schema = load_schema()
    v = Draft202012Validator(schema)

    words_599 = "word " * 599
    words_600 = "word " * 600
    base = {
        "paper_id": "ml_3f9a2c7b",
        "paper_title": "Gaussian Widgets",
        "arm": "neutral",
        "model": "gpt-5",
        "decoding": {"temperature": 0, "top_p": 1},
        "persona_version": "A",
        "content_scope": "FULL+FIG",
        "helpfulness_1to7": 4,
        "toxicity_1to7": 2,
        "harshness_1to7": 3,
        "run_id": "pilot001",
        "timestamp_iso": "2025-08-09T13:00:00+09:00",
        "source_type": "your-library",
        "paper_url": "https://example.org/paper.pdf",
        "fig_mode": "VISION",
        "judge_model": "Claude",
        "toxicity_flag_tau5": False,
        "notes": ""
    }

    bad = dict(base, review_text=words_599.strip(), word_count=599)
    errs_bad = list(v.iter_errors(bad))
    assert errs_bad, "expected schema to reject <600 words"

    good = dict(base, review_text=words_600.strip(), word_count=600)
    errs_good = list(v.iter_errors(good))
    assert not errs_good, f"unexpected errors: {[e.message for e in errs_good]}"
