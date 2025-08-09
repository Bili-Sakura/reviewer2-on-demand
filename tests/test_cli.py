from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.r2 import app  # uses your existing CLI
from src.cli.r2 import qc as qc_cmd  # to check exit codes


runner = CliRunner()


def calc_pid(title: str) -> str:
    return "ml_" + hashlib.blake2s(title.lower().encode("utf-8")).hexdigest()[:8]


def write_inputs_csv(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["paper_title", "paper_url", "source_type"])
        for r in rows:
            w.writerow([r["paper_title"], r["paper_url"], r["source_type"]])


def normalize_for_snapshot(obj: dict) -> dict:
    obj = dict(obj)
    obj["timestamp_iso"] = "<TS>"
    return obj


def test_review_command_writes_expected_stubs(tmp_path: Path):
    # Arrange
    paper = {
        "paper_title": "Gaussian Widgets",
        "paper_url": "https://example.org/paper.pdf",
        "source_type": "your-library",
    }
    csv_path = tmp_path / "papers.csv"
    write_inputs_csv(csv_path, [paper])

    # Act
    result = runner.invoke(app, ["review", "--run-id", "pilot001", "--list", str(csv_path)])
    assert result.exit_code == 0, result.output

    # Assert file content
    out_jsonl = tmp_path / "outputs" / "aggregates" / "run_pilot001.jsonl"
    assert out_jsonl.exists(), "JSONL not created"

    with out_jsonl.open(encoding="utf-8") as f:
        lines = [json.loads(x) for x in f if x.strip()]

    # 3 arms
    assert len(lines) == 3
    expected_pid = calc_pid(paper["paper_title"])

    # Load snapshot
    snapshot_path = Path(__file__).parent / "snapshots" / "cli_review_snapshot.jsonl"
    expected_lines = [json.loads(x) for x in snapshot_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    # Normalize timestamps then compare
    lines_norm = [normalize_for_snapshot(x) for x in lines]
    assert all(x["paper_id"] == expected_pid for x in lines_norm)
    assert lines_norm == expected_lines

    # QC should pass on stubs
    qc_result = runner.invoke(app, ["qc", "--in-jsonl", str(out_jsonl)])
    assert qc_result.exit_code == 0, qc_result.output
