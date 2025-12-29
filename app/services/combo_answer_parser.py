"""Deterministic parsing for combo answers."""
from __future__ import annotations

ALLOWED_EMOTIONS = {"pressure", "panic", "self_doubt", "motivation"}


def normalize_gap(value: str) -> str:
    lowered = (value or "").lower()
    if "big" in lowered:
        return "big gap"
    if "small" in lowered:
        return "small gap"
    return lowered.strip()[:30]


def normalize_emotion(value: str) -> str | None:
    lowered = (value or "").lower()
    for emotion in ALLOWED_EMOTIONS:
        if emotion in lowered:
            return emotion
    if "anx" in lowered or "panic" in lowered:
        return "panic"
    if "doubt" in lowered or "worth" in lowered:
        return "self_doubt"
    if "pressure" in lowered or "expect" in lowered:
        return "pressure"
    if "motivat" in lowered or "hope" in lowered:
        return "motivation"
    return None


def parse_friend_compare_emotion(answer_text: str):
    """Parse 3-line combo answer for friend/comparison/emotion."""
    lines = [ln.strip() for ln in (answer_text or "").splitlines() if ln.strip()]
    if len(lines) < 3:
        return None

    friend = lines[0][:50]

    if "|" not in lines[1]:
        return None
    person, gap = [part.strip() for part in lines[1].split("|", 1)]
    person = person[:50]
    gap = normalize_gap(gap)

    emotion = normalize_emotion(lines[2])
    if not emotion:
        return None

    return {
        "slots": {
            "distractions.friend_name": friend,
            "social_comparison.comparison_person": person,
            "social_comparison.comparison_gap": gap,
        },
        "emotion": emotion,
    }


def parse_distraction_time_combo(answer_text: str):
    """Parse 3-line distraction/time combo."""
    lines = [ln.strip() for ln in (answer_text or "").splitlines() if ln.strip()]
    if len(lines) < 3:
        return None

    game = lines[0][:80]
    gaming_time = lines[1][:80]
    breaker = lines[2][:80]

    return {
        "slots": {
            "distractions.gaming_app": game,
            "distractions.gaming_time": gaming_time,
            "time_pressure.timetable_breaker": breaker,
        },
        "emotion": None,
    }


PARSERS = {
    "friend_compare_emotion": parse_friend_compare_emotion,
    "distraction_time_combo": parse_distraction_time_combo,
}


__all__ = ["parse_friend_compare_emotion", "parse_distraction_time_combo", "PARSERS"]
