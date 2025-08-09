from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Iterator, Any


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def resolve_openreview_or_arxiv(url: str) -> str:
    """Return a direct PDF URL if possible; otherwise pass through.

    This is a lightweight placeholder; extend with real resolution rules.
    """
    return url


def download_pdf(url: str, dest: Path) -> Path:
    """Download a PDF to dest if not present; returns the destination path.

    Uses urllib to avoid external dependencies. Simple idempotent cache.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError

    resolved = resolve_openreview_or_arxiv(url)
    try:
        with urlopen(resolved, timeout=60) as resp:
            data = resp.read()
        atomic_write(dest, data)
        return dest
    except (URLError, HTTPError) as e:
        raise RuntimeError(f"Failed to download PDF: {resolved} -> {e}") from e
