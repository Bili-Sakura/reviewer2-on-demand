from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any


def extract_full_text(pdf_path: Path) -> Dict[str, Any]:
    """Extract title, abstract, and structured sections from a PDF.

    Placeholder implementation. Integrate MinerU or pdfminer here.
    """
    raise NotImplementedError("MinerU/text extraction not implemented yet")


def extract_figures(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract figures with image paths, captions, and IDs.

    Placeholder implementation. Integrate figure extraction here.
    """
    raise NotImplementedError("Figure extraction not implemented yet")
