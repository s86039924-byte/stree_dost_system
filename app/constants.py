"""Domain schema and priority definitions."""
from __future__ import annotations

SLOT_SCHEMA = {
    "distractions": [
        "phone_app",
        "app_activity",
        "reel_type",
        "friend_name",
        "gaming_app",
        "gaming_time",
    ],
    "academic_confidence": [
        "weak_subject",
        "favorite_subject",
        "concept_confidence",
        "last_test_experience",
    ],
    "time_pressure": [
        "exam_time_left",
        "study_hours_per_day",
        "timetable_breaker",
    ],
    "social_comparison": [
        "comparison_person",
        "comparison_gap",
    ],
    "family_pressure": [
        "family_member",
        "expectation_type",
    ],
    "motivation": [
        "motivation_reason",
        "demotivation_reason",
    ],
    "backlog_stress": [
        "backlog_subject",
        "backlog_deadline",
    ],
}

PRIORITY_ORDER = [
    "time_pressure",
    "academic_confidence",
    "distractions",
    "backlog_stress",
    "family_pressure",
    "social_comparison",
    "motivation",
]


__all__ = ["SLOT_SCHEMA", "PRIORITY_ORDER"]
