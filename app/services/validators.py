"""Question validators."""
from __future__ import annotations

import re

_BANNED = [
    r"\bwhy\b",
    r"\btherapy\b",
    r"\bcounsel(or|ing)\b",
    r"\bmental health\b",
    r"\bdiagnos(is|e)\b",
    r"\btrauma\b",
    r"\bdepress(ed|ion)\b",
]


def is_valid_question(question: str) -> bool:
    """Validate generated question against domain rules."""
    if not question:
        return False

    question = " ".join(question.strip().split())

    if question.count("?") != 1 or not question.endswith("?"):
        return False

    if len(question.split()) > 24:
        return False

    lowered = question.lower()
    for pattern in _BANNED:
        if re.search(pattern, lowered):
            return False

    if re.search(r",\s*(and|also)\s+", lowered):
        return False

    if re.search(r"\band\b.*\b(tell|share|explain|describe|mention)\b", lowered):
        return False

    if ";" in question or "/" in question:
        return False

    return True


__all__ = ["is_valid_question"]
