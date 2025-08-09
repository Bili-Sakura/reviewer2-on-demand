from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ReviewerClient:
    model_id: str = "gpt-5"
    temperature: int = 0
    top_p: int = 1

    def review(self, messages: List[Dict[str, Any]], images: List[Any] | None = None) -> str:
        """Send messages (and optional images) to the reviewer model.

        Implement using your provider SDK. Must enforce temperature=0, top_p=1.
        """
        raise NotImplementedError


@dataclass
class JudgeClient:
    model_id: str = "claude"

    def score_helpfulness(self, title: str, abstract: str, review: str) -> int:
        raise NotImplementedError

    def score_toxicity(self, review: str) -> int:
        raise NotImplementedError

    def score_harshness(self, review: str) -> int:
        raise NotImplementedError
