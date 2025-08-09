from __future__ import annotations

import hashlib


def paper_id_from_title(title: str) -> str:
    """Compute paper_id as ml_ + blake2s(lower(title))[:8] hex.

    Parameters
    ----------
    title: str
        Paper title which may contain mixed case and punctuation.

    Returns
    -------
    str
        Identifier of the form ml_XXXXXXXX
    """
    digest = hashlib.blake2s(title.lower().encode("utf-8")).hexdigest()[:8]
    return f"ml_{digest}"
