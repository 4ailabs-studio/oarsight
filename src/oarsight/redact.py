"""Minimal redaction of personal identifiers before analysis.

The transcript itself is never modified; redaction applies only to the copy an
analysis model sees. Names spoken in free conversation cannot be detected
reliably and are NOT covered; the audio itself is still sent to the speech
model. Only fictional or role-played consultations are used in development.
"""

from __future__ import annotations

import re

# 8+ digits allowing separators, optional +52 / area code. Plain short numbers
# (doses, lab values, years) have fewer digits and pass through untouched.
_PHONE = re.compile(r"(?<!\d)(?:\+?52[\s.\-]?)?(?:\(?\d{2,3}\)?[\s.\-]?)?\d{3,4}[\s.\-]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Mexican CURP: 4 letters + 6 digits + H/M + 5 letters + 2 digits.
_CURP = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}\d{2}\b", re.IGNORECASE)
# IMSS social-security number: 11 digits.
_NSS = re.compile(r"(?<!\d)\d{11}(?!\d)")
# Dates of birth in common written forms.
_DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b\d{1,2} de [a-záéíóúñ]+ de \d{4}\b",
    re.IGNORECASE,
)

_PATTERNS = (
    (_EMAIL, "[CORREO]"),
    (_CURP, "[CURP]"),
    (_NSS, "[NSS]"),
    (_PHONE, "[TELÉFONO]"),
    (_DATE, "[FECHA]"),
)


def redact(text: str) -> tuple[str, int]:
    """Return (redacted text, number of spans replaced)."""
    count = 0
    for pattern, token in _PATTERNS:
        text, n = pattern.subn(token, text)
        count += n
    return text, count
