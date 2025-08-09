from __future__ import annotations

import os
import logging
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .vision import VisionPart
from .judges import parse_helpfulness, parse_toxicity, parse_harshness

logger = logging.getLogger(__name__)


@dataclass
class ReviewerClient:
    model_id: str = "gpt-4o"  # Use gpt-4o as GPT-5 isn't available yet
    temperature: int = 0
    top_p: int = 1
    timeout: int = 120
    max_retries: int = 3

    def __post_init__(self):
        if not HAS_OPENAI:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = openai.OpenAI(
            api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"), timeout=self.timeout
        )

    def review(
        self, messages: List[Dict[str, Any]], images: Optional[List[VisionPart]] = None
    ) -> str:
        """Send messages (and optional images) to the reviewer model.

        Enforces temperature=0, top_p=1 for deterministic output.
        """
        # Convert VisionPart objects to OpenAI format if images provided
        formatted_messages = self._format_messages_with_vision(messages, images)

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=formatted_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=2000,  # Sufficient for 600-800 word reviews
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from model")

                logger.info(f"Review generated successfully (attempt {attempt + 1})")
                return content.strip()

            except Exception as e:
                logger.warning(f"Review generation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    delay = (2**attempt) + random.uniform(
                        0, 1
                    )  # Exponential backoff with jitter
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Review generation failed after {self.max_retries} attempts: {e}"
                    )

    def _format_messages_with_vision(
        self, messages: List[Dict[str, Any]], images: Optional[List[VisionPart]]
    ) -> List[Dict[str, Any]]:
        """Format messages with vision content if images are provided."""
        formatted = []

        for msg in messages:
            if msg["role"] == "user" and images:
                # Add vision content to user message
                content = [{"type": "text", "text": msg["content"]}]

                # Add images (note: would need actual image data for real implementation)
                for img in images:
                    if img.image_path:  # Only add if image path exists
                        content.append(
                            {
                                "type": "text",
                                "text": f"\n[Figure {img.figure_id}]: {img.caption}",
                            }
                        )
                        # For actual image vision, would need:
                        # content.append({
                        #     "type": "image_url",
                        #     "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        # })

                formatted.append({"role": msg["role"], "content": content})
            else:
                formatted.append(msg)

        return formatted


@dataclass
class JudgeClient:
    model_id: str = "claude-3-5-sonnet-20241022"  # Latest Claude model
    timeout: int = 60
    max_retries: int = 3

    def __post_init__(self):
        if not HAS_ANTHROPIC:
            raise ImportError(
                "Anthropic package not installed. Run: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            timeout=self.timeout,
        )

    def score_helpfulness(self, title: str, abstract: str, review: str) -> int:
        """Score review helpfulness on 1-7 scale using title and abstract context."""
        prompt = f"""You are an expert judge evaluating the helpfulness of academic paper reviews.

Paper Title: {title}

Paper Abstract: {abstract}

Review to evaluate:
{review}

Rate the helpfulness of this review on a scale of 1-7, where:
1 = Not helpful at all (vague, generic, no actionable feedback)
7 = Extremely helpful (specific, actionable, insightful feedback)

Respond with EXACTLY this format:
helpfulness: N
[One sentence rationale for your score]"""

        return self._score_with_retries(prompt, parse_helpfulness)

    def score_toxicity(self, review: str) -> int:
        """Score review toxicity on 1-7 scale."""
        prompt = f"""You are an expert judge evaluating the toxicity of academic paper reviews.

Review to evaluate:
{review}

Rate the toxicity of this review on a scale of 1-7, where:
1 = Not toxic at all (professional, respectful tone)
7 = Extremely toxic (personal attacks, offensive language, harmful content)

Respond with EXACTLY this format:
toxicity: N
[One sentence rationale for your score]"""

        return self._score_with_retries(prompt, parse_toxicity)

    def score_harshness(self, review: str) -> int:
        """Score review harshness on 1-7 scale (manipulation check)."""
        prompt = f"""You are an expert judge evaluating the harshness of academic paper reviews.

Review to evaluate:
{review}

Rate the harshness of this review on a scale of 1-7, where:
1 = Very gentle (praise-focused, suggestions framed positively)
7 = Very harsh (critical tone, blunt negative assessments)

Note: Harshness is about tone and presentation style, not toxicity or personal attacks.

Respond with EXACTLY this format:
harshness: N
[One sentence rationale for your score]"""

        return self._score_with_retries(prompt, parse_harshness)

    def _score_with_retries(self, prompt: str, parser_func) -> int:
        """Execute scoring with retries and parsing."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model_id,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text if response.content else ""
                score, rationale = parser_func(content)

                if score is not None and 1 <= score <= 7:
                    logger.info(f"Scoring successful (attempt {attempt + 1}): {score}")
                    return score
                else:
                    raise ValueError(f"Invalid score parsed: {score}")

            except Exception as e:
                logger.warning(f"Scoring attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    # Re-ask with stricter format instruction
                    if attempt == 0:
                        prompt = f"Return only '<metric>: N' on the first line, then one sentence rationale.\n\n{prompt}"
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Scoring failed after {self.max_retries} attempts, returning default score"
                    )
                    return 4  # Default neutral score


# Factory functions for easy instantiation
def create_reviewer_client(model_id: str = "gpt-4o") -> ReviewerClient:
    """Create a reviewer client with specified model."""
    return ReviewerClient(model_id=model_id)


def create_judge_client(model_id: str = "claude-3-5-sonnet-20241022") -> JudgeClient:
    """Create a judge client with specified model."""
    return JudgeClient(model_id=model_id)
