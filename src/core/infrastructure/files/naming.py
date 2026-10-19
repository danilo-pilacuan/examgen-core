"""File-name helpers shared by the pipeline and the API.

The exam artifacts (PDFs, ZIP) use a human-readable slug derived from the
exam name the professor requested (e.g. "Midterm 1" -> "Midterm_1"), never
a random hash, so the downloads are intuitive.
"""
from __future__ import annotations

import re
import unicodedata


def slugify(name: str) -> str:
    """Normalizes a name into a safe file-name slug.

    Example: "Midterm 1 — Economía" -> "Midterm_1_Economia"

    Removes accents, spaces -> underscores, drops non-alphanumeric
    characters and collapses repeated separators.
    """
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[\s]+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_\-.]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_-.")


def version_letter(index: int) -> str:
    """Letter of an exam version: 0 -> A, 1 -> B, ... 9 -> J."""
    return chr(ord("A") + max(0, min(index, 25)))
