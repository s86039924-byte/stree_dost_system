"""Generic fallback questions per domain."""
from __future__ import annotations

GENERIC_DOMAIN_QUESTIONS = {
    "distractions": {
        "slot": "general_distraction",
        "question": "What do you usually do on your phone when you feel low or tired?",
    },
    "academic_confidence": {
        "slot": "exam_feeling",
        "question": "What makes the exam feel especially heavy for you right now?",
    },
}


def get_generic_domain_question(domain: str) -> tuple[str, str] | None:
    config = GENERIC_DOMAIN_QUESTIONS.get(domain)
    if not config:
        return None
    return config["slot"], config["question"]


def get_generic_slot_name(domain: str) -> str | None:
    config = GENERIC_DOMAIN_QUESTIONS.get(domain)
    if not config:
        return None
    return config["slot"]


__all__ = ["GENERIC_DOMAIN_QUESTIONS", "get_generic_domain_question", "get_generic_slot_name"]
