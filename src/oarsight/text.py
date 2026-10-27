"""Text helpers shared by the verifiers."""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str | None) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces. Used to compare quotes with the transcript."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    letters = re.sub(r"[^a-z0-9ñ ]", " ", without_accents)
    return re.sub(r"\s+", " ", letters).strip()


def is_literal_quote(quote: str | None, source: str) -> bool:
    """True if `quote` appears in `source`, ignoring case, accents and punctuation. Empty quotes never count."""
    q = normalize(quote)
    return bool(q) and q in normalize(source)
