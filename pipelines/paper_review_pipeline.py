"""
Paper Review Pipeline

A high-level pipeline for end-to-end paper processing and review using MinerU parser and LLM reviewer.
"""

import os
import json
import logging
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from dataclasses import asdict

from .config import PaperReviewConfig, MinerUConfig, LLMConfig
from src.minerU.minerU import MinerUClient
from src.llms.dashscope_client import DashScopeClient


logger = logging.getLogger(__name__)


class PaperReviewPipeline:
    """
    End-to-end pipeline for paper processing and review.

    This pipeline combines MinerU paper parsing with LLM-based review to provide
    comprehensive paper evaluation for top-tier ML conferences.
    """

    def __init__(self, config: Optional[PaperReviewConfig] = None, **kwargs):
        """
        Initialize the Paper Review Pipeline.

        Args:
            config: Configuration object for the pipeline
            **kwargs: Additional configuration parameters
        """
        self.config = config or PaperReviewConfig(**kwargs)

        # Initialize components
        self._init_mineru()
        self._init_llm()

        logger.info("Paper Review Pipeline initialized successfully")

    def _init_mineru(self):
        """Initialize MinerU client."""
        try:
            self.mineru_client = MinerUClient(api_key=self.config.mineru.api_key)
            logger.info("MinerU client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MinerU client: {e}")
            raise

    def _init_llm(self):
        """Initialize LLM client."""
        try:
            self.llm_client = DashScopeClient(
                api_key=self.config.llm.api_key, model=self.config.llm.model_name
            )
            logger.info(
                f"LLM client initialized with model: {self.config.llm.model_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise

    def __call__(
        self, inputs: Union[str, List[str]], conference: str = "auto", **kwargs
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process papers and generate reviews.

        Args:
            inputs: Paper URL(s) or file path(s)
            conference: Target conference (icml, neurips, iclr, aaaai, auto)
            **kwargs: Additional parameters

        Returns:
            Review results for the papers
        """
        if isinstance(inputs, str):
            return self._process_single_paper(inputs, conference, **kwargs)
        else:
            return self._process_multiple_papers(inputs, conference, **kwargs)

    def _process_single_paper(
        self, input_path: str, conference: str = "auto", **kwargs
    ) -> Dict[str, Any]:
        """Process a single paper."""
        logger.info(f"Processing paper: {input_path}")

        # Step 1: Parse paper with MinerU
        parsed_content = self._parse_paper(input_path, **kwargs)

        # Step 2: Generate review with LLM
        review = self._generate_review(parsed_content, conference, **kwargs)

        # Step 3: Compile results
        result = {
            "input": input_path,
            "conference": conference,
            "parsed_content": parsed_content,
            "review": review,
            "timestamp": self._get_timestamp(),
        }

        # Save results if configured
        if self.config.save_review_results:
            self._save_results(result, input_path)

        return result

    def _process_multiple_papers(
        self, input_paths: List[str], conference: str = "auto", **kwargs
    ) -> List[Dict[str, Any]]:
        """Process multiple papers."""
        logger.info(f"Processing {len(input_paths)} papers")

        results = []
        for input_path in input_paths:
            try:
                result = self._process_single_paper(input_path, conference, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {input_path}: {e}")
                results.append(
                    {
                        "input": input_path,
                        "error": str(e),
                        "timestamp": self._get_timestamp(),
                    }
                )

        return results

    def _parse_paper(self, input_path: str, **kwargs) -> Dict[str, Any]:
        """Parse paper using MinerU."""
        logger.info(f"Parsing paper: {input_path}")

        # Determine if input is URL or file path
        if input_path.startswith(("http://", "https://")):
            output_file = self.mineru_client.parse_from_url(
                input_path,
                output_dir=self.config.mineru.output_dir,
                is_ocr=self.config.mineru.is_ocr,
                enable_formula=self.config.mineru.enable_formula,
                enable_table=self.config.mineru.enable_table,
                language=self.config.mineru.language,
                model_version=self.config.mineru.model_version,
                max_wait_time=self.config.mineru.max_wait_time,
                **kwargs,
            )
        else:
            output_file = self.mineru_client.parse_from_file(
                input_path,
                output_dir=self.config.mineru.output_dir,
                is_ocr=self.config.mineru.is_ocr,
                enable_formula=self.config.mineru.enable_formula,
                enable_table=self.config.mineru.enable_table,
                language=self.config.mineru.language,
                model_version=self.config.mineru.model_version,
                max_wait_time=self.config.mineru.max_wait_time,
                **kwargs,
            )

        # Read parsed content
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "output_file": output_file,
            "content": content,
            "file_size": len(content),
            "parsing_config": asdict(self.config.mineru),
        }

    def _generate_review(
        self, parsed_content: Dict[str, Any], conference: str = "auto", **kwargs
    ) -> Dict[str, Any]:
        """Generate review using LLM."""
        logger.info("Generating review with LLM")

        # Prepare prompt
        prompt = self._prepare_review_prompt(parsed_content, conference)

        # Generate review
        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=self.config.llm.system_prompt,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
            **kwargs,
        )

        # Parse response
        review = self._parse_review_response(response, conference)

        return {
            "raw_response": response,
            "parsed_review": review,
            "llm_config": asdict(self.config.llm),
        }

    def _prepare_review_prompt(
        self, parsed_content: Dict[str, Any], conference: str
    ) -> str:
        """Prepare a minimal scoring-only prompt for the LLM."""
        content = parsed_content["content"]

        # Truncate content if too long
        max_length = 8000  # Leave room for prompt and response
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated due to length]"

        prompt = (
            "You are a reviewer for top-tier machine learning conferences. "
            "Read the paper content below and output only a single integer from 1 to 10 "
            "that reflects the overall acceptance readiness for a top-tier conference. "
            "1 = far below bar, 5 = borderline/uncertain, 10 = award-level. "
            "Output exactly the integer only, with no words or symbols.\n\n"
            "Paper Content:\n" + content
        )

        return prompt

    def _get_conference_info(self, conference: str) -> Dict[str, Any]:
        """Get information about the target conference."""
        if conference == "auto":
            # Default to NeurIPS standards
            conference = "neurips"

        conference = conference.lower()
        if conference not in self.config.conference_standards:
            logger.warning(f"Unknown conference: {conference}, using NeurIPS standards")
            conference = "neurips"

        standards = self.config.conference_standards[conference]
        conference_names = {
            "icml": "International Conference on Machine Learning (ICML)",
            "neurips": "Neural Information Processing Systems (NeurIPS)",
            "iclr": "International Conference on Learning Representations (ICLR)",
            "aaai": "AAAI Conference on Artificial Intelligence (AAAI)",
        }

        return {
            "name": conference_names.get(conference, conference.upper()),
            "acceptance_rate": standards["acceptance_rate"],
            "min_confidence": standards["min_confidence"],
        }

    def _parse_review_response(self, response: str, conference: str) -> Dict[str, Any]:
        """Parse the LLM response expecting a single integer 1-10."""
        import re

        try:
            text = (response or "").strip()
            # First try exact integer in the whole response
            if re.fullmatch(r"(10|[1-9])", text):
                score = int(text)
            else:
                # Fallback: find the first standalone 1-10 integer
                m = re.search(r"\b(10|[1-9])\b", text)
                score = int(m.group(1)) if m else 5

            # Clamp to 1-10 just in case
            score = max(1, min(10, score))

            return {"score": score}
        except Exception as e:
            logger.warning(f"Failed to parse score from response: {e}")
            return {"score": 5, "parsing_error": str(e)}

    def _save_results(self, result: Dict[str, Any], input_path: str):
        """Save review results to file."""
        try:
            # Create output filename
            input_name = Path(input_path).stem
            if input_path.startswith(("http://", "https://")):
                input_name = input_name or "url_paper"

            output_file = (
                Path(self.config.mineru.output_dir)
                / f"{input_name}_review.{self.config.output_format}"
            )

            if self.config.output_format == "json":
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
            elif self.config.output_format == "markdown":
                self._save_as_markdown(result, output_file)
            else:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(str(result))

            logger.info(f"Results saved to: {output_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def _save_as_markdown(self, result: Dict[str, Any], output_file: Path):
        """Save results in markdown format."""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Paper Review Results\n\n")
            f.write(f"**Input:** {result['input']}\n")
            f.write(f"**Conference:** {result['conference']}\n")
            f.write(f"**Timestamp:** {result['timestamp']}\n\n")

            f.write(f"## Review Score\n\n")
            review = result["review"]["parsed_review"]
            f.write(f"- **Score:** {review.get('score', 'N/A')}/10\n\n")

            f.write(f"## Full Review\n\n")
            f.write(
                f"{result['review'].get('full_response') or result['review'].get('raw_response', '')}\n\n"
            )

            f.write(f"## Parsed Content\n\n")
            f.write(
                f"*Content length: {result['parsed_content']['file_size']} characters*\n\n"
            )
            f.write(
                f"```markdown\n{result['parsed_content']['content'][:1000]}...\n```\n"
            )

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()

    def save_pretrained(self, save_directory: str):
        """Save the pipeline configuration."""
        save_directory = Path(save_directory)
        save_directory.mkdir(parents=True, exist_ok=True)

        # Save config
        config_file = save_directory / "config.json"
        with open(config_file, "w") as f:
            json.dump(asdict(self.config), f, indent=2)

        logger.info(f"Pipeline configuration saved to: {save_directory}")

    @classmethod
    def from_pretrained(cls, save_directory: str, **kwargs):
        """Load pipeline from saved configuration."""
        config_file = Path(save_directory) / "config.json"

        if not config_file.exists():
            raise ValueError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            config_dict = json.load(f)

        # Reconstruct config objects
        mineru_config = MinerUConfig(**config_dict["mineru"])
        llm_config = LLMConfig(**config_dict["llm"])

        # Remove component configs from main config
        main_config_dict = {
            k: v for k, v in config_dict.items() if k not in ["mineru", "llm"]
        }

        config = PaperReviewConfig(
            mineru=mineru_config, llm=llm_config, **main_config_dict
        )

        return cls(config, **kwargs)
