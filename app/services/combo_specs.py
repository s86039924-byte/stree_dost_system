"""Combo question specifications."""
from __future__ import annotations

COMBO_SPECS = {
    "friend_compare_emotion": {
        "domains": ["distractions", "social_comparison"],
        "slots": [
            ("distractions", "friend_name"),
            ("social_comparison", "comparison_person"),
            ("social_comparison", "comparison_gap"),
        ],
        "emotion_probe": True,
        "answer_format": "3 lines",
        "hint": (
            "Line1 friend name\n"
            "Line2 comparison person | gap(small/big)\n"
            "Line3 emotion: pressure/panic/self_doubt/motivation"
        ),
    },
    "distraction_time_combo": {
        "domains": ["distractions", "time_pressure"],
        "slots": [
            ("distractions", "gaming_app"),
            ("distractions", "gaming_time"),
            ("time_pressure", "timetable_breaker"),
        ],
        "emotion_probe": False,
        "answer_format": "3 lines",
        "hint": (
            "Line1 games you play most (e.g., COD / PUBG / Free Fire)\n"
            "Line2 gaming time per day (e.g., 2-3 hours)\n"
            "Line3 biggest timetable breaker (phone/games/friends/laziness)"
        ),
    },
}


FORBIDDEN_COMBOS = [
    {"emotion", "comparison"},
    {"comparison", "distraction"},
    {"emotion", "distraction"},
]


__all__ = ["COMBO_SPECS", "FORBIDDEN_COMBOS"]
