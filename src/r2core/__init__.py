"""Core library for Reviewer #2 pipeline.

Modules include hashing, IO, extraction, vision packaging, prompts,
model clients, review post-processing, judge parsing, QC, orchestration,
and chart helpers.
"""

from .hashing import paper_id_from_title  # re-export for convenience

__all__ = [
    "paper_id_from_title",
]
