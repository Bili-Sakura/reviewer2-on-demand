#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Dict, Any

import typer

app = typer.Typer(help="Reviewer #2 — end-to-end CLI (pilot-ready)")

# ---------- utils ----------

JST = timezone.utc  # placeholder; set proper JST offset below


def now_jst_iso() -> str:
    # Asia/Tokyo is UTC+9 without DST
    from datetime import timedelta
    jst = timezone(timedelta(hours=9))
    return datetime.now(tz=jst).isoformat(timespec="seconds")


def paper_id_from_title(title: str) -> str:
    h = hashlib.blake2s(title.lower().encode("utf-8")).hexdigest()[:8]
    return f"ml_{h}"


def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def read_paper_list(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "paper_title": row["paper_title"].strip(),
                "paper_url": row["paper_url"].strip(),
                "source_type": row["source_type"].strip(),
            })
    return rows


def make_full20_stub(
    paper: Dict[str, str],
    paper_id: str,
    arm: str,
    run_id: str,
) -> Dict[str, Any]:
    return {
        "paper_id": paper_id,
        "paper_title": paper["paper_title"],
        "arm": arm,
        "model": "gpt-5",
        "decoding": {"temperature": 0, "top_p": 1},
        "persona_version": "A",
        "content_scope": "FULL+FIG",
        "review_text": "",
        "word_count": 0,
        "helpfulness_1to7": None,
        "toxicity_1to7": None,
        "harshness_1to7": None,
        "run_id": run_id,
        "timestamp_iso": now_jst_iso(),
        "source_type": paper["source_type"],
        "paper_url": paper["paper_url"],
        "fig_mode": "VISION",
        "judge_model": "Claude",
        "toxicity_flag_tau5": False,
        "notes": ""
    }


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ---------- commands ----------

@app.command()
def ingest(
    list: Path = typer.Option(..., exists=True, help="CSV with paper_title,paper_url,source_type"),
    run_id: str = typer.Option(..., help="Run identifier, e.g., pilot001"),
):
    """
    Resolve and cache metadata; compute paper_ids.
    (PDF download/extraction happens in later stages or external modules.)
    """
    rows = read_paper_list(list)
    out_dir = Path("outputs") / "reviews"
    ensure_dirs(out_dir)

    info_rows = []
    for row in rows:
        pid = paper_id_from_title(row["paper_title"])
        info_rows.append({"paper_id": pid, **row})
    # Save a manifest for the run
    manifest = Path("outputs") / "aggregates" / f"manifest_{run_id}.json"
    ensure_dirs(manifest.parent)
    manifest.write_text(json.dumps(info_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.secho(f"Ingested {len(info_rows)} papers → {manifest}", fg=typer.colors.GREEN)


@app.command()
def review(
    run_id: str = typer.Option(...),
    list: Path = typer.Option(..., exists=True),
    arms: str = typer.Option("praise,neutral,harsh", help="Comma-separated"),
):
    """
    Create FULL-20 JSONL stubs (one per arm per paper).
    Hook your model orchestration where indicated (TODO blocks).
    """
    rows = read_paper_list(list)
    out_jsonl = Path("outputs") / "aggregates" / f"run_{run_id}.jsonl"
    ensure_dirs(out_jsonl.parent)

    arm_list = [a.strip() for a in arms.split(",") if a.strip()]
    for paper in rows:
        pid = paper_id_from_title(paper["paper_title"])
        for arm in arm_list:
            line = make_full20_stub(paper, pid, arm, run_id)

            # TODO: integrate MinerU extraction + figure packaging
            # TODO: build persona A prompt (tone + ICLR structure)
            # TODO: call GPT-5 (T=0, top_p=1), enforce 600–800 words
            # TODO: fill review_text and word_count; then call judges and fill scores
            append_jsonl(out_jsonl, line)

    typer.secho(f"Wrote stubs to {out_jsonl}", fg=typer.colors.GREEN)


@app.command()
def judge(
    run_id: str = typer.Option(...),
    in_jsonl: Path = typer.Option(..., exists=True, help="JSONL with filled review_text/word_count"),
):
    """
    Read JSONL, call judges (Claude) for helpfulness/toxicity/harshness, update lines.
    This is a placeholder demonstrating IO; wire your JudgeClient here.
    """
    out_jsonl = Path("outputs") / "aggregates" / f"judged_{run_id}.jsonl"
    ensure_dirs(out_jsonl.parent)

    with in_jsonl.open(encoding="utf-8") as fin, out_jsonl.open("w", encoding="utf-8") as fout:
        for line in fin:
            obj = json.loads(line)
            # TODO: replace with real judge calls + parsing
            if obj.get("review_text", ""):
                # placeholder: keep nulls; your real code sets 1–7 integers and tau5 flag
                obj["toxicity_flag_tau5"] = bool(
                    isinstance(obj.get("toxicity_1to7"), int) and obj["toxicity_1to7"] >= 5
                )
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    typer.secho(f"Judged file → {out_jsonl}", fg=typer.colors.GREEN)


@app.command()
def qc(
    in_jsonl: Path = typer.Option(..., exists=True),
):
    """
    Lightweight QC: check keys and basic constraints.
    For full validation, run this against the JSON Schema using jsonschema.
    """
    import re
    required_keys = {
        "paper_id","paper_title","arm","model","decoding","persona_version","content_scope",
        "review_text","word_count","helpfulness_1to7","toxicity_1to7","harshness_1to7",
        "run_id","timestamp_iso","source_type","paper_url","fig_mode","judge_model",
        "toxicity_flag_tau5","notes"
    }
    ok = True
    count = 0
    with in_jsonl.open(encoding="utf-8") as f:
        for line in f:
            count += 1
            obj = json.loads(line)
            if set(obj.keys()) != required_keys:
                ok = False
                typer.secho(f"[keys] mismatch on line {count}", fg=typer.colors.RED)
            if obj.get("review_text", ""):
                wc = obj.get("word_count", 0)
                if not (600 <= wc <= 800):
                    ok = False
                    typer.secho(f"[len] word_count {wc} out of range on line {count}", fg=typer.colors.RED)
    if ok:
        typer.secho("QC passed ✅", fg=typer.colors.GREEN)
    else:
        raise typer.Exit(code=1)


@app.command()
def aggregate(
    files: List[Path] = typer.Argument(..., exists=True),
    out: Path = typer.Option(Path("outputs/aggregates/combined.jsonl")),
):
    """Concatenate multiple JSONLs."""
    ensure_dirs(out.parent)
    with out.open("w", encoding="utf-8") as fout:
        for fp in files:
            with fp.open(encoding="utf-8") as fin:
                for line in fin:
                    fout.write(line)
    typer.secho(f"Aggregated → {out}", fg=typer.colors.GREEN)


@app.command()
def all(
    list: Path = typer.Option(..., exists=True),
    run_id: str = typer.Option(...),
):
    """
    Convenience wrapper; currently just makes stubs.
    Extend to call extraction, review, judge, qc in sequence.
    """
    ingest.callback  # no-op to appease linters
    review(list=list, run_id=run_id)  # extend as you hook in other stages
    typer.secho("All done (stubs). Wire models to go end-to-end.", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
