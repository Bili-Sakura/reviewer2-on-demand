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

from r2core.hashing import paper_id_from_title
from r2core.io import append_jsonl, download_pdf
from r2core.mineru import extract_full_text, extract_figures
from r2core.models import create_reviewer_client, create_judge_client
from r2core.prompts import build_review_prompt
from r2core.review import word_count, enforce_window, validate_structure
from r2core.vision import package_figures

app = typer.Typer(help="Reviewer #2 — end-to-end CLI (pilot-ready)")

# ---------- utils ----------

JST = timezone.utc  # placeholder; set proper JST offset below


def now_jst_iso() -> str:
    # Asia/Tokyo is UTC+9 without DST
    from datetime import timedelta

    jst = timezone(timedelta(hours=9))
    return datetime.now(tz=jst).isoformat(timespec="seconds")


# removed local paper_id_from_title (use r2core.hashing)


def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def read_paper_list(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "paper_title": row["paper_title"].strip(),
                    "paper_url": row["paper_url"].strip(),
                    "source_type": row["source_type"].strip(),
                }
            )
    return rows


# removed local append_jsonl (use r2core.io)


def make_full20_stub(
    paper: Dict[str, str], paper_id: str, arm: str, run_id: str
) -> Dict[str, Any]:
    """Create a FULL-20 JSONL stub with metadata filled."""
    return {
        "paper_id": paper_id,
        "paper_title": paper["paper_title"],
        "arm": arm,
        "model": "gpt-4o",  # Updated to use available model
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
        "notes": "",
    }


# ---------- commands ----------


@app.command()
def ingest(
    list: Path = typer.Option(
        ..., exists=True, help="CSV with paper_title,paper_url,source_type"
    ),
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
    manifest.write_text(
        json.dumps(info_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.secho(f"Ingested {len(info_rows)} papers → {manifest}", fg=typer.colors.GREEN)


@app.command()
def review(
    run_id: str = typer.Option(...),
    list: Path = typer.Option(..., exists=True),
    arms: str = typer.Option("praise,neutral,harsh", help="Comma-separated"),
    skip_download: bool = typer.Option(False, help="Skip PDF download (use cached)"),
):
    """
    Generate complete reviews with real model calls.
    Downloads PDFs, extracts content, generates reviews, and scores them.
    """
    rows = read_paper_list(list)
    out_jsonl = Path("outputs") / "aggregates" / f"run_{run_id}.jsonl"
    pdf_dir = Path("data") / "papers"
    ensure_dirs(out_jsonl.parent, pdf_dir)

    arm_list = [a.strip() for a in arms.split(",") if a.strip()]

    # Initialize clients
    try:
        reviewer = create_reviewer_client()
        judge = create_judge_client()
        typer.secho("✅ Model clients initialized", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ Failed to initialize model clients: {e}", fg=typer.colors.RED)
        typer.secho(
            "💡 Make sure to set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    total_papers = len(rows)
    total_reviews = total_papers * len(arm_list)

    typer.secho(
        f"📄 Processing {total_papers} papers × {len(arm_list)} arms = {total_reviews} reviews",
        fg=typer.colors.BLUE,
    )

    for paper_idx, paper in enumerate(rows, 1):
        pid = paper_id_from_title(paper["paper_title"])
        typer.secho(
            f"\n[{paper_idx}/{total_papers}] Processing: {paper['paper_title'][:50]}...",
            fg=typer.colors.CYAN,
        )

        # Download PDF
        pdf_path = pdf_dir / f"{pid}.pdf"
        if not skip_download or not pdf_path.exists():
            try:
                typer.echo(f"  📥 Downloading PDF...")
                download_pdf(paper["paper_url"], pdf_path)
                typer.echo(f"  ✅ PDF cached: {pdf_path}")
            except Exception as e:
                typer.secho(f"  ❌ PDF download failed: {e}", fg=typer.colors.RED)
                continue

        # Extract content
        try:
            typer.echo(f"  📖 Extracting text and figures...")
            content = extract_full_text(pdf_path)
            figures = extract_figures(pdf_path)
            content["figures"] = figures
            typer.echo(
                f"  ✅ Extracted {len(content.get('sections', []))} sections, {len(figures)} figures"
            )
        except Exception as e:
            typer.secho(f"  ❌ Content extraction failed: {e}", fg=typer.colors.RED)
            continue

        # Generate reviews for each arm
        for arm in arm_list:
            typer.echo(f"  🤖 Generating {arm} review...")
            line = make_full20_stub(paper, pid, arm, run_id)

            try:
                # Build prompt
                prompt_bundle = build_review_prompt(arm, meta=paper, content=content)

                # Generate review
                raw_review = reviewer.review(
                    prompt_bundle.messages, prompt_bundle.images
                )

                # Post-process review
                review_text = enforce_window(raw_review, 600, 800)
                if not validate_structure(review_text):
                    line["notes"] += "structure_validation_failed;"

                wc = word_count(review_text)
                line.update(
                    {
                        "review_text": review_text,
                        "word_count": wc,
                        "timestamp_iso": now_jst_iso(),
                    }
                )

                # Score with judges
                typer.echo(f"    📊 Scoring review...")
                helpfulness = judge.score_helpfulness(
                    paper["paper_title"], content.get("abstract", ""), review_text
                )
                toxicity = judge.score_toxicity(review_text)
                harshness = judge.score_harshness(review_text)

                line.update(
                    {
                        "helpfulness_1to7": helpfulness,
                        "toxicity_1to7": toxicity,
                        "harshness_1to7": harshness,
                        "toxicity_flag_tau5": bool(toxicity >= 5),
                    }
                )

                typer.echo(
                    f"    ✅ {arm}: {wc} words, H={helpfulness}, T={toxicity}, H={harshness}"
                )

            except Exception as e:
                typer.secho(f"    ❌ {arm} review failed: {e}", fg=typer.colors.RED)
                line["notes"] += f"generation_failed:{str(e)[:100]};"

            # Save result
            append_jsonl(out_jsonl, line)

    typer.secho(f"\n🎉 Complete! Results saved to {out_jsonl}", fg=typer.colors.GREEN)
    typer.secho(
        f"💡 Run validation: python scripts/validate_jsonl.py --jsonl {out_jsonl}",
        fg=typer.colors.YELLOW,
    )


@app.command()
def judge(
    run_id: str = typer.Option(...),
    in_jsonl: Path = typer.Option(
        ..., exists=True, help="JSONL with filled review_text/word_count"
    ),
):
    """
    Read JSONL, call judges (Claude) for helpfulness/toxicity/harshness, update lines.
    This is a placeholder demonstrating IO; wire your JudgeClient here.
    """
    out_jsonl = Path("outputs") / "aggregates" / f"judged_{run_id}.jsonl"
    ensure_dirs(out_jsonl.parent)

    with in_jsonl.open(encoding="utf-8") as fin, out_jsonl.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            obj = json.loads(line)
            # TODO: replace with real judge calls + parsing
            if obj.get("review_text", ""):
                # placeholder: keep nulls; your real code sets 1–7 integers and tau5 flag
                obj["toxicity_flag_tau5"] = bool(
                    isinstance(obj.get("toxicity_1to7"), int)
                    and obj["toxicity_1to7"] >= 5
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
        "paper_id",
        "paper_title",
        "arm",
        "model",
        "decoding",
        "persona_version",
        "content_scope",
        "review_text",
        "word_count",
        "helpfulness_1to7",
        "toxicity_1to7",
        "harshness_1to7",
        "run_id",
        "timestamp_iso",
        "source_type",
        "paper_url",
        "fig_mode",
        "judge_model",
        "toxicity_flag_tau5",
        "notes",
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
                    typer.secho(
                        f"[len] word_count {wc} out of range on line {count}",
                        fg=typer.colors.RED,
                    )
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
    End-to-end pipeline: ingest, review generation, and QC.
    """
    typer.secho("🚀 Starting end-to-end pipeline...", fg=typer.colors.BLUE)

    # Step 1: Ingest
    typer.secho("\n📋 Step 1: Ingesting paper metadata...", fg=typer.colors.BLUE)
    ingest(list=list, run_id=run_id)

    # Step 2: Review generation
    typer.secho("\n🤖 Step 2: Generating reviews...", fg=typer.colors.BLUE)
    review(list=list, run_id=run_id)

    # Step 3: QC
    typer.secho("\n🔍 Step 3: Quality control...", fg=typer.colors.BLUE)
    out_jsonl = Path("outputs") / "aggregates" / f"run_{run_id}.jsonl"
    qc(in_jsonl=out_jsonl)

    typer.secho(
        f"\n🎉 Pipeline complete! Results in {out_jsonl}", fg=typer.colors.GREEN
    )


if __name__ == "__main__":
    app()
