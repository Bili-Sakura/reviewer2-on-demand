from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from .vision import VisionPart


def build_persona_line(arm: str) -> str:
    mapping = {
        "praise": "Act as a supportive mentor reviewer. Start with strengths. Phrase critiques as suggestions. Be specific. No toxicity.",
        "neutral": "Act as an impartial senior reviewer. Balance strengths and weaknesses. Evidence-first. Professional tone.",
        "harsh": "Act as a tough, exacting reviewer. Lead with major flaws. Blunt and concise. No insults or slurs.",
    }
    try:
        return mapping[arm]
    except KeyError as e:
        raise ValueError(f"Unknown arm: {arm}") from e


@dataclass
class PromptBundle:
    messages: List[Dict[str, Any]]
    images: List[VisionPart]


def build_review_prompt(arm: str, meta: Dict[str, Any], content: Dict[str, Any]) -> PromptBundle:
    persona = build_persona_line(arm)
    structure = (
        "Use the ICLR/OpenReview structure: Summary; Strengths; Weaknesses; Questions; "
        "Overall [1–10]; Confidence [1–5]. Keep the review to 600–800 words."
    )
    title = meta.get("paper_title", "")
    abstract = content.get("abstract", meta.get("abstract", ""))

    # Abridged main text
    sections = content.get("sections", [])
    joined_sections = []
    for sec in sections:
        heading = sec.get("heading", "")
        body = sec.get("text", "")
        if heading:
            joined_sections.append(f"{heading}: {body}")
        else:
            joined_sections.append(body)
    main_text = "\n\n".join(joined_sections)[:20000]

    images = content.get("figures", [])
    vision_parts = [
        VisionPart(
            image_path=str(f.get("image_path", "")),
            caption=str(f.get("caption", "")),
            figure_id=str(f.get("figure_id", "")),
        )
        for f in images
    ]

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": f"{persona} {structure}"},
        {
            "role": "user",
            "content": (
                f"Title: {title}\n\n"
                f"Abstract: {abstract}\n\n"
                f"Main text (abridged):\n{main_text}\n\n"
                "Critique the paper’s content; avoid personal remarks; keep non-toxic."
            ),
        },
    ]
    return PromptBundle(messages=messages, images=vision_parts)
