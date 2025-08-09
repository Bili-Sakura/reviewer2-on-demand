from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class VisionPart:
    image_path: str
    caption: str
    figure_id: str


def package_figures(figs: List[dict]) -> List[VisionPart]:
    packaged: List[VisionPart] = []
    for idx, f in enumerate(figs, start=1):
        caption = f.get("caption") or f"Figure {idx} (no caption extracted)."
        packaged.append(
            VisionPart(
                image_path=str(f.get("image_path", "")),
                caption=str(caption),
                figure_id=str(f.get("figure_id", idx)),
            )
        )
    return packaged
