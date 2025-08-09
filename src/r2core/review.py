from __future__ import annotations

import re
from typing import Tuple


_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _normalize_whitespace(text: str) -> str:
    text = _CODE_BLOCK_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_count(text: str) -> int:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return 0
    return len(normalized.split(" "))


def enforce_window(text: str, min_w: int = 600, max_w: int = 800) -> str:
    wc = word_count(text)
    if wc == 0:
        return text
    if wc < min_w:
        return text  # leave expansion to a model turn handled upstream
    if wc <= max_w:
        return text
    # Truncate: try to cut at sentence boundaries without dropping headers
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for s in sentences:
        candidate = (" ".join(out + [s])).strip()
        if word_count(candidate) <= max_w:
            out.append(s)
        else:
            break
    truncated = " ".join(out).strip()
    if not truncated:
        # Fallback: hard token trim
        tokens = _normalize_whitespace(text).split(" ")[:max_w]
        truncated = " ".join(tokens)
    return truncated


def validate_structure(text: str) -> bool:
    headers = [
        "Summary",
        "Strengths",
        "Weaknesses",
        "Questions",
        "Overall",
        "Confidence",
    ]
    return all(h in text for h in headers)


def parse_overall_confidence(text: str) -> Tuple[int | None, int | None]:
    overall = None
    confidence = None
    m1 = re.search(r"Overall\s*\[?\s*(\d{1,2})\s*\]?", text)
    if m1:
        try:
            overall = int(m1.group(1))
        except ValueError:
            overall = None
    m2 = re.search(r"Confidence\s*\[?\s*(\d{1,2})\s*\]?", text)
    if m2:
        try:
            confidence = int(m2.group(1))
        except ValueError:
            confidence = None
    return overall, confidence
