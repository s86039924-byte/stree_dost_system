"""Canned fallback questions per domain slot."""
from __future__ import annotations

FALLBACK_QUESTIONS = {
    "distractions": {
        "phone_app": "Which app distracts you most while studying?",
        "app_activity": "What do you usually do on that app?",
        "reel_type": "What kind of reels do you watch most?",
        "friend_name": "Which friend distracts you most?",
        "gaming_app": "Which game do you play most?",
        "gaming_time": "When do you usually play games?",
    },
    "academic_confidence": {
        "weak_subject": "Which subject troubles you most?",
        "favorite_subject": "Which subject do you enjoy most?",
        "concept_confidence": "How confident are you with core concepts?",
        "last_test_experience": "How was your last test experience?",
    },
    "time_pressure": {
        "exam_time_left": "How much time is left for your exam?",
        "study_hours_per_day": "How many hours do you study daily?",
        "timetable_breaker": "What breaks your study timetable most?",
    },
    "social_comparison": {
        "comparison_person": "Who do you compare yourself with most?",
        "comparison_gap": "Is the gap between you and them big?",
    },
    "family_pressure": {
        "family_member": "Which family member pressures you most?",
        "expectation_type": "What do they expect most from you?",
    },
    "motivation": {
        "motivation_reason": "What motivates you to study?",
        "demotivation_reason": "What demotivates you the most?",
    },
    "backlog_stress": {
        "backlog_subject": "Which subject backlog worries you most?",
        "backlog_deadline": "When is the next exam for that backlog?",
    },
}


CLARIFIER_QUESTION = "Please answer in 2–4 words."


__all__ = ["FALLBACK_QUESTIONS", "CLARIFIER_QUESTION"]
