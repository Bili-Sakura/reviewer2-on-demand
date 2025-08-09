from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from .hashing import paper_id_from_title
from .io import append_jsonl
from .prompts import build_review_prompt
from .review import word_count, enforce_window, validate_structure


def run_one_paper(paper: Dict[str, Any], run_id: str, out_jsonl: Path) -> Dict[str, Any]:
    paper_id = paper_id_from_title(paper["paper_title"])

    # Extraction would happen here (text + figures)
    content: Dict[str, Any] = {"abstract": "", "sections": [], "figures": []}

    results: List[Dict[str, Any]] = []
    for arm in ["praise", "neutral", "harsh"]:
        prompt = build_review_prompt(arm, meta=paper, content=content)
        # Model call would go here
        review_text = ""  # placeholder
        review_text = enforce_window(review_text, 600, 800)
        assert validate_structure(review_text) or review_text == ""
        wc = word_count(review_text)

        line = {
            "paper_id": paper_id,
            "paper_title": paper["paper_title"],
            "arm": arm,
            "model": "gpt-5",
            "decoding": {"temperature": 0, "top_p": 1},
            "persona_version": "A",
            "content_scope": "FULL+FIG",
            "review_text": review_text,
            "word_count": wc,
            "helpfulness_1to7": None,
            "toxicity_1to7": None,
            "harshness_1to7": None,
            "run_id": run_id,
            "timestamp_iso": "",
            "source_type": paper.get("source_type", ""),
            "paper_url": paper.get("paper_url", ""),
            "fig_mode": "VISION",
            "judge_model": "Claude",
            "toxicity_flag_tau5": False,
            "notes": "",
        }
        append_jsonl(out_jsonl, line)
        results.append(line)
    return {"paper_id": paper_id, "results": results}
