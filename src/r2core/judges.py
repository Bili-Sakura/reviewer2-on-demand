from __future__ import annotations

import re
from typing import Tuple


_HELPFULNESS_RE = re.compile(r"helpfulness:\s*([1-7])", re.IGNORECASE)
_TOXICITY_RE = re.compile(r"toxicity:\s*([1-7])", re.IGNORECASE)
_HARSHNESS_RE = re.compile(r"harshness:\s*([1-7])", re.IGNORECASE)


def parse_helpfulness(text: str) -> Tuple[int | None, str]:
    m = _HELPFULNESS_RE.search(text)
    score = int(m.group(1)) if m else None
    rationale = text.strip().split("\n", 1)[-1] if "\n" in text else ""
    return score, rationale


def parse_toxicity(text: str) -> Tuple[int | None, str]:
    m = _TOXICITY_RE.search(text)
    score = int(m.group(1)) if m else None
    rationale = text.strip().split("\n", 1)[-1] if "\n" in text else ""
    return score, rationale


def parse_harshness(text: str) -> Tuple[int | None, str]:
    m = _HARSHNESS_RE.search(text)
    score = int(m.group(1)) if m else None
    rationale = text.strip().split("\n", 1)[-1] if "\n" in text else ""
    return score, rationale
