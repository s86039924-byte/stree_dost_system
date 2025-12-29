"""Stop condition helpers."""
from __future__ import annotations


def should_stop(
    *,
    total_questions_asked: int,
    missing_slots_count: int,
    min_questions: int,
    max_questions: int,
) -> bool:
    """Return True when session should stop asking questions."""
    if total_questions_asked >= max_questions:
        return True

    if total_questions_asked >= min_questions and missing_slots_count == 0:
        return True

    return False


__all__ = ["should_stop"]
