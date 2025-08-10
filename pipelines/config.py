"""
Configuration classes for the Paper Review Pipeline.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path


@dataclass
class MinerUConfig:
    """Configuration for MinerU paper parser."""

    api_key: Optional[str] = None
    is_ocr: bool = True
    enable_formula: bool = True
    enable_table: bool = True
    language: str = "auto"
    model_version: str = "v2"
    output_dir: str = "./parsed_papers"
    max_wait_time: int = 3600


@dataclass
class LLMConfig:
    """Configuration for LLM reviewer."""

    model_name: str = "openrouter/anthropic/claude-3.5-sonnet"
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4000
    system_prompt: str = field(
        default_factory=lambda: """You are an expert reviewer for top-tier machine learning conferences (ICML, NeurIPS, ICLR, ICML, AAAI). 
    
Your task is to evaluate research papers and provide:
1. Overall assessment (Accept/Reject/Revision)
2. Confidence score (1-10)
3. Detailed reasoning
4. Strengths and weaknesses
5. Specific recommendations for improvement

Be thorough, fair, and constructive in your evaluation."""
    )

    review_criteria: List[str] = field(
        default_factory=lambda: [
            "Novelty and contribution",
            "Technical soundness",
            "Experimental evaluation",
            "Clarity and presentation",
            "Relevance to ML community",
        ]
    )


@dataclass
class PaperReviewConfig:
    """Main configuration for the Paper Review Pipeline."""

    # Pipeline settings
    cache_dir: Optional[str] = None
    device: str = "auto"
    torch_dtype: str = "auto"

    # Component configurations
    mineru: MinerUConfig = field(default_factory=MinerUConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Output settings
    save_parsed_content: bool = True
    save_review_results: bool = True
    output_format: str = "json"  # json, markdown, txt

    # Review settings
    conference_standards: Dict[str, Any] = field(
        default_factory=lambda: {
            "icml": {"acceptance_rate": 0.22, "min_confidence": 7},
            "neurips": {"acceptance_rate": 0.20, "min_confidence": 7},
            "iclr": {"acceptance_rate": 0.32, "min_confidence": 6},
            "aaai": {"acceptance_rate": 0.25, "min_confidence": 6},
        }
    )

    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.cache_dir is None:
            self.cache_dir = Path.home() / ".cache" / "paper_review_pipeline"

        # Ensure output directories exist
        Path(self.mineru.output_dir).mkdir(parents=True, exist_ok=True)

        # Set environment variables for API keys
        if self.mineru.api_key:
            import os

            os.environ["MINERU_API_KEY"] = self.mineru.api_key

        if self.llm.api_key:
            import os

            os.environ["OPENROUTER_API_KEY"] = self.llm.api_key
