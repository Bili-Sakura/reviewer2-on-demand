from __future__ import annotations

import re
import json
import subprocess
import tempfile
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import fitz  # PyMuPDF

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from .config import get_mineru_config

logger = logging.getLogger(__name__)


def extract_full_text(pdf_path: Path) -> Dict[str, Any]:
    """Extract title, abstract, and structured sections from a PDF.

    Uses MinerU as primary method, falls back to PyMuPDF then pdfplumber.
    Returns structured content for review generation.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    config = get_mineru_config()

    # Try MinerU first if enabled
    if config.get("enabled", True):
        try:
            return _extract_with_mineru(pdf_path, config)
        except Exception as e:
            logger.warning(f"MinerU extraction failed: {e}, falling back to PyMuPDF")

    # Fallback to PyMuPDF (better for academic papers)
    if HAS_PYMUPDF:
        try:
            result = _extract_with_pymupdf(pdf_path)
            result["notes"] = result.get("notes", "") + "mineru_fallback;"
            return result
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}, trying pdfplumber")

    # Fallback to pdfplumber
    if HAS_PDFPLUMBER:
        try:
            result = _extract_with_pdfplumber(pdf_path)
            result["notes"] = result.get("notes", "") + "mineru_fallback;"
            return result
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

    # Last resort: basic text extraction
    result = _extract_basic_text(pdf_path)
    result["notes"] = result.get("notes", "") + "mineru_fallback;"
    return result


def _extract_with_mineru(pdf_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text using MinerU API or CLI tool."""
    # Try API first if API key is available
    api_key = os.getenv("MINERU_API_KEY")
    if api_key and HAS_REQUESTS:
        try:
            return _extract_with_mineru_api(pdf_path, config, api_key)
        except Exception as e:
            logger.warning(f"MinerU API extraction failed: {e}, falling back to CLI")

    # Fallback to CLI tool
    return _extract_with_mineru_cli(pdf_path, config)


def _extract_with_mineru_api(
    pdf_path: Path, config: Dict[str, Any], api_key: str
) -> Dict[str, Any]:
    """Extract text using MinerU API."""
    base_url = os.getenv("MINERU_BASE_URL", "https://mineru.net/api")

    # Prepare the file for upload
    with open(pdf_path, "rb") as pdf_file:
        files = {"file": (pdf_path.name, pdf_file, "application/pdf")}

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        # Add configuration data
        data = {
            "keep_layout": config.get("keep_layout", True),
            "include_appendix": config.get("include_appendix", True),
        }

        # Make API request
        response = requests.post(
            f"{base_url}/extract",
            files=files,
            data=data,
            headers=headers,
            timeout=300,  # 5-minute timeout
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"MinerU API failed with status {response.status_code}: {response.text}"
            )

        # Parse response
        result = response.json()

        if "error" in result:
            raise RuntimeError(f"MinerU API error: {result['error']}")

        # Extract content from API response
        markdown_content = result.get("markdown", "")
        metadata = result.get("metadata", {})

        if not markdown_content:
            raise RuntimeError("MinerU API did not return markdown content")

        # Convert to structured format
        return _parse_mineru_output(markdown_content, metadata, config)


def _extract_with_mineru_cli(pdf_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text using MinerU CLI tool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_dir = temp_path / "output"
        output_dir.mkdir(exist_ok=True)

        # Prepare MinerU command
        cmd = ["mineru", "-p", str(pdf_path), "-o", str(output_dir)]

        # Add configuration options if needed
        if config.get("keep_layout", True):
            # MinerU keeps layout by default, no specific flag needed
            pass

        # Run MinerU
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute timeout
                check=True,
            )
            logger.debug(f"MinerU output: {result.stdout}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("MinerU extraction timeout (5 minutes)")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"MinerU failed with code {e.returncode}: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "MinerU command not found. Ensure 'mineru' is installed and in PATH"
            )

        # Find output files
        pdf_name = pdf_path.stem
        markdown_file = None
        json_file = None

        # Look for output files
        for file in output_dir.rglob("*"):
            if file.suffix == ".md":
                markdown_file = file
            elif file.suffix == ".json":
                json_file = file

        if not markdown_file:
            raise RuntimeError("MinerU did not produce expected markdown output")

        # Parse markdown content
        markdown_content = markdown_file.read_text(encoding="utf-8")

        # Parse JSON metadata if available
        metadata = {}
        if json_file:
            try:
                metadata = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to parse MinerU JSON metadata: {e}")

        # Convert markdown to structured format
        return _parse_mineru_output(markdown_content, metadata, config)


def _parse_mineru_output(
    markdown_content: str, metadata: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse MinerU markdown output into structured format."""
    lines = markdown_content.split("\n")

    # Extract title (usually the first heading)
    title = _extract_title_from_markdown(lines)

    # Extract abstract
    abstract = _extract_abstract_from_markdown(markdown_content)

    # Extract sections
    sections = _extract_sections_from_markdown(markdown_content)

    # Extract appendix if configured
    appendix = []
    if config.get("include_appendix", True):
        appendix = _extract_appendix_from_markdown(markdown_content)

    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "appendix": appendix,
        "extraction_method": "mineru",
        "notes": "",
        "metadata": metadata,  # Include any additional metadata from MinerU
    }


def _extract_title_from_markdown(lines: List[str]) -> str:
    """Extract title from markdown lines."""
    for line in lines[:20]:  # Check first 20 lines
        line = line.strip()
        # Look for top-level heading
        if line.startswith("# ") and len(line) > 3:
            return line[2:].strip()
        # Or look for substantial text that could be a title
        elif len(line) > 10 and not line.startswith(
            ("#", "##", "###", "*", "-", "[", "!")
        ):
            # Clean up title formatting
            line = re.sub(r"\s+", " ", line)
            if not line.lower().startswith(("arxiv:", "doi:", "http", "abstract")):
                return line
    return "Unknown Title"


def _extract_abstract_from_markdown(content: str) -> str:
    """Extract abstract from markdown content."""
    # Look for Abstract section
    abstract_patterns = [
        r"(?i)#+\s*abstract\s*\n(.*?)(?=\n#+|\n\n|\Z)",
        r"(?i)\*\*abstract\*\*[:\s]*(.*?)(?=\n\*\*|\n\n|\Z)",
        r"(?i)abstract[:\s]*(.*?)(?=\n#+|\n\n|\Z)",
    ]

    for pattern in abstract_patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            # Clean up markdown formatting
            abstract = re.sub(r"\*\*(.*?)\*\*", r"\1", abstract)  # Remove bold
            abstract = re.sub(r"\*(.*?)\*", r"\1", abstract)  # Remove italic
            abstract = re.sub(r"\s+", " ", abstract)  # Normalize whitespace
            return abstract[:2000]  # Limit length

    return ""


def _extract_sections_from_markdown(content: str) -> List[Dict[str, Any]]:
    """Extract sections from markdown content."""
    sections = []

    # Split by headings (# ## ### etc.)
    section_pattern = r"(^#+\s+.+$)"
    parts = re.split(section_pattern, content, flags=re.MULTILINE)

    current_heading = None
    current_text = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this is a heading
        if re.match(r"^#+\s+", part):
            # Save previous section
            if current_heading and current_text:
                sections.append(
                    {
                        "heading": current_heading,
                        "text": "\n".join(current_text).strip(),
                    }
                )

            # Start new section
            current_heading = re.sub(r"^#+\s+", "", part).strip()
            current_text = []
        else:
            # Add to current section
            if current_heading:
                current_text.append(part)

    # Add final section
    if current_heading and current_text:
        sections.append(
            {"heading": current_heading, "text": "\n".join(current_text).strip()}
        )

    # If no sections found, create a single content section
    if not sections:
        sections.append(
            {"heading": "Content", "text": content[:10000]}  # Limit to first 10k chars
        )

    return sections


def _extract_appendix_from_markdown(content: str) -> List[Dict[str, Any]]:
    """Extract appendix from markdown content."""
    appendix = []

    # Look for appendix section
    appendix_pattern = r"(?i)(#+\s*appendix.*?)(?=\n#+\s*(?:references|bibliography)|$)"
    match = re.search(appendix_pattern, content, re.DOTALL)

    if match:
        appendix_content = match.group(1).strip()
        appendix.append(
            {
                "heading": "Appendix",
                "text": appendix_content[:5000],  # Limit appendix length
            }
        )

    return appendix


def _extract_with_pymupdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using PyMuPDF with section detection."""
    doc = fitz.open(pdf_path)

    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"

    doc.close()

    return _parse_academic_structure(full_text)


def _extract_with_pdfplumber(pdf_path: Path) -> Dict[str, Any]:
    """Extract text using pdfplumber."""
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    return _parse_academic_structure(full_text)


def _extract_basic_text(pdf_path: Path) -> Dict[str, Any]:
    """Minimal extraction fallback."""
    logger.error("No PDF libraries available, returning minimal structure")
    return {
        "title": pdf_path.stem,  # Use filename as title
        "abstract": "",
        "sections": [
            {
                "heading": "Content",
                "text": "PDF extraction failed - no libraries available",
            }
        ],
        "appendix": [],
        "extraction_method": "fallback",
        "notes": "pdf_extraction_failed",
    }


def _parse_academic_structure(text: str) -> Dict[str, Any]:
    """Parse academic paper structure from raw text."""
    lines = text.split("\n")

    # Extract title (usually first few lines, often in caps or large font)
    title = _extract_title(lines)

    # Extract abstract
    abstract = _extract_abstract(text)

    # Extract sections
    sections = _extract_sections(text)

    # Extract appendix
    appendix = _extract_appendix(text)

    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "appendix": appendix,
        "extraction_method": "pymupdf" if HAS_PYMUPDF else "pdfplumber",
        "notes": "",
    }


def _extract_title(lines: List[str]) -> str:
    """Extract paper title from first few lines."""
    # Look for the first substantial line (likely the title)
    for line in lines[:10]:
        line = line.strip()
        if len(line) > 10 and not line.lower().startswith(("arxiv:", "doi:", "http")):
            # Clean up common title formatting
            line = re.sub(r"\s+", " ", line)
            return line

    return "Unknown Title"


def _extract_abstract(text: str) -> str:
    """Extract abstract section."""
    # Look for abstract section
    abstract_pattern = r"(?i)abstract\s*[:\-]?\s*(.*?)(?=\n\s*(?:1\.?\s*introduction|keywords|index terms|\n\s*\n))"
    match = re.search(abstract_pattern, text, re.DOTALL)

    if match:
        abstract = match.group(1).strip()
        # Clean up abstract text
        abstract = re.sub(r"\s+", " ", abstract)
        return abstract[:2000]  # Limit length

    # Fallback: look for text after "Abstract" keyword
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^\s*abstract\s*$", line, re.IGNORECASE):
            # Take next few lines as abstract
            abstract_lines = []
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].strip() and not re.match(r"^\s*\d+\.?\s*[A-Z]", lines[j]):
                    abstract_lines.append(lines[j].strip())
                elif abstract_lines:  # Stop at next section
                    break
            return " ".join(abstract_lines)[:2000]

    return ""


def _extract_sections(text: str) -> List[Dict[str, Any]]:
    """Extract paper sections with headings."""
    sections = []

    # Common section patterns in academic papers
    section_patterns = [
        r"^\s*(\d+\.?\s+[A-Z][^.\n]{3,50})\s*$",  # "1. Introduction"
        r"^\s*([A-Z][A-Z\s]{2,30})\s*$",  # "INTRODUCTION"
        r"^\s*(\d+\.\d+\.?\s+[A-Z][^.\n]{3,50})\s*$",  # "1.1. Background"
    ]

    lines = text.split("\n")
    current_section = None
    current_text = []

    for line in lines:
        is_heading = False

        # Check if this line looks like a section heading
        for pattern in section_patterns:
            if re.match(pattern, line.strip()):
                is_heading = True

                # Save previous section
                if current_section:
                    sections.append(
                        {
                            "heading": current_section,
                            "text": "\n".join(current_text).strip(),
                        }
                    )

                # Start new section
                current_section = line.strip()
                current_text = []
                break

        if not is_heading and current_section:
            current_text.append(line)

    # Add final section
    if current_section:
        sections.append(
            {"heading": current_section, "text": "\n".join(current_text).strip()}
        )

    # If no sections found, create a single content section
    if not sections:
        sections.append(
            {"heading": "Content", "text": text[:10000]}  # Limit to first 10k chars
        )

    return sections


def _extract_appendix(text: str) -> List[Dict[str, Any]]:
    """Extract appendix sections."""
    appendix = []

    # Look for appendix section
    appendix_match = re.search(
        r"(?i)(appendix.*?)(?=references|bibliography|$)", text, re.DOTALL
    )

    if appendix_match:
        appendix_text = appendix_match.group(1)
        appendix.append(
            {
                "heading": "Appendix",
                "text": appendix_text.strip()[:5000],  # Limit appendix length
            }
        )

    return appendix


def extract_figures(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract figures with image paths, captions, and IDs.

    Uses MinerU for enhanced figure extraction when available,
    falls back to text-based figure reference extraction.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    config = get_mineru_config()
    figures = []

    # Try MinerU for figure extraction if enabled
    if config.get("enabled", True):
        try:
            figures = _extract_figures_with_mineru(pdf_path)
            if figures:
                return figures
        except Exception as e:
            logger.warning(
                f"MinerU figure extraction failed: {e}, falling back to text extraction"
            )

    # Fallback: extract figure references from text
    try:
        content = extract_full_text(pdf_path)
        full_text = ""
        for section in content.get("sections", []):
            full_text += section.get("text", "") + "\n"

        # Find figure references
        figure_pattern = r"(?i)figure\s+(\d+)[:\.]?\s*([^.\n]{10,200})"
        matches = re.finditer(figure_pattern, full_text)

        for i, match in enumerate(matches, 1):
            figure_num = match.group(1)
            caption = match.group(2).strip()

            figures.append(
                {
                    "figure_id": f"fig_{figure_num}",
                    "image_path": "",  # Would need actual image extraction
                    "caption": caption[:300],  # Limit caption length
                    "page_num": None,  # Would need page tracking
                    "extraction_method": "text_reference",
                }
            )

            if len(figures) >= 10:  # Limit number of figures
                break

    except Exception as e:
        logger.warning(f"Figure extraction failed: {e}")

    return figures


def _extract_figures_with_mineru(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract figures using MinerU's enhanced capabilities."""
    # Try API first if API key is available
    api_key = os.getenv("MINERU_API_KEY")
    if api_key and HAS_REQUESTS:
        try:
            return _extract_figures_with_mineru_api(pdf_path, api_key)
        except Exception as e:
            logger.warning(
                f"MinerU API figure extraction failed: {e}, falling back to CLI"
            )

    # Fallback to CLI tool
    return _extract_figures_with_mineru_cli(pdf_path)


def _extract_figures_with_mineru_api(
    pdf_path: Path, api_key: str
) -> List[Dict[str, Any]]:
    """Extract figures using MinerU API."""
    base_url = os.getenv("MINERU_BASE_URL", "https://mineru.net/api")

    with open(pdf_path, "rb") as pdf_file:
        files = {"file": (pdf_path.name, pdf_file, "application/pdf")}
        headers = {"Authorization": f"Bearer {api_key}"}
        data = {"extract_figures": True}

        response = requests.post(
            f"{base_url}/extract",
            files=files,
            data=data,
            headers=headers,
            timeout=300,
        )

        if response.status_code != 200:
            raise RuntimeError(f"MinerU API failed: {response.status_code}")

        result = response.json()
        figures = []

        # Extract figures from API response
        for i, figure_data in enumerate(result.get("figures", []), 1):
            figures.append(
                {
                    "figure_id": f"fig_{i}",
                    "image_path": figure_data.get("image_url", ""),
                    "caption": figure_data.get("caption", f"Figure {i}")[:300],
                    "page_num": figure_data.get("page_num"),
                    "extraction_method": "mineru_api",
                }
            )

            if len(figures) >= 10:  # Limit number of figures
                break

        return figures


def _extract_figures_with_mineru_cli(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract figures using MinerU CLI tool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_dir = temp_path / "output"
        output_dir.mkdir(exist_ok=True)

        # Run MinerU
        cmd = ["mineru", "-p", str(pdf_path), "-o", str(output_dir)]

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            raise RuntimeError(f"MinerU figure extraction failed: {e}")

        figures = []

        # Look for extracted images and markdown content
        markdown_file = None
        image_files = []

        for file in output_dir.rglob("*"):
            if file.suffix == ".md":
                markdown_file = file
            elif file.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".svg"]:
                image_files.append(file)

        if markdown_file:
            markdown_content = markdown_file.read_text(encoding="utf-8")

            # Extract figures from markdown with enhanced detection
            figure_patterns = [
                r"!\[([^\]]*)\]\(([^)]+)\)",  # ![caption](image_path)
                r"(?i)figure\s+(\d+)[:\.]?\s*([^.\n]{10,300})",  # Figure N: caption
            ]

            figure_count = 0
            for pattern in figure_patterns:
                matches = re.finditer(pattern, markdown_content)
                for match in matches:
                    if pattern.startswith("!"):  # Markdown image syntax
                        caption = match.group(1) or f"Figure {figure_count + 1}"
                        image_path = match.group(2)
                    else:  # Figure reference
                        figure_num = match.group(1)
                        caption = match.group(2).strip()
                        image_path = ""

                    figures.append(
                        {
                            "figure_id": f"fig_{figure_count + 1}",
                            "image_path": image_path,
                            "caption": caption[:300],
                            "page_num": None,
                            "extraction_method": "mineru_cli",
                        }
                    )

                    figure_count += 1
                    if figure_count >= 10:  # Limit number of figures
                        break

                if figure_count >= 10:
                    break

        return figures
