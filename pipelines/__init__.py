"""
Paper Review Pipeline

A high-level pipeline for end-to-end paper processing and review using MinerU parser and LLM reviewer.
"""

from .paper_review_pipeline import PaperReviewPipeline
from .config import PaperReviewConfig

__version__ = "0.1.0"
__all__ = ["PaperReviewPipeline", "PaperReviewConfig"]
