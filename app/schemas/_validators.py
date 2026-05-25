"""Shared field-level normalizers used by multiple Pydantic schemas."""

from __future__ import annotations

import re


def normalize_us_zip(value: str | None) -> str | None:
    """Accept any reasonable US zip input, return canonical form or None.

    Canonical forms returned:
      - 5-digit:  "97201"
      - ZIP+4:    "97201-1234"

    Accepted inputs (all normalize to one of the above):
      - "97201", "97201 ", "  97201  "       -> "97201"
      - "97201-1234", "972011234"            -> "97201-1234"
      - "97201 1234", "97201.1234"           -> "97201-1234"  (any non-digit separator)

    Empty / None / whitespace-only -> None.
    Anything else (wrong digit count, leading zeros stripped, etc.) raises ValueError.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None

    # Fast path: already canonical.
    if re.fullmatch(r"\d{5}", raw):
        return raw
    if re.fullmatch(r"\d{5}-\d{4}", raw):
        return raw

    # Tolerant path: strip all non-digits and infer.
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 5:
        return digits
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"

    raise ValueError(
        "Zip code must be 5 digits (e.g. 97201) or ZIP+4 (e.g. 97201-1234)."
    )
