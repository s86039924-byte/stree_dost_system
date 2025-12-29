"""Negation-aware relevance helpers."""
from __future__ import annotations

import re
from typing import Iterable

NEGATORS = {
    "not",
    "no",
    "never",
    "dont",
    "don't",
    "do not",
    "isnt",
    "isn't",
    "am not",
    "aren't",
    "without",
}

DOMAIN_DENIAL_PATTERNS: dict[str, list[str]] = {
    "distractions": [
        r"\bnot distracted by (my )?(phone|mobile|instagram|reels|games|friends?)\b",
        r"\bno (phone|mobile|friends?) distraction\b",
        r"\b(phone|mobile) (does not|doesn't) distract\b",
        r"\bi am not distracted by (phone|mobile|friends?)\b",
    ],
    "social_comparison": [
        r"\b(i )?(dont|don't|do not) compare\b",
        r"\bno comparison\b",
        r"\bnot comparing\b",
    ],
}

DOMAIN_KEYWORDS = {
    "distractions": [
        "phone",
        "instagram",
        "youtube",
        "reels",
        "game",
        "gaming",
        "pubg",
        "bgmi",
        "free fire",
        "call of duty",
        "cod",
    ],
    "time_pressure": [
        "time",
        "timetable",
        "schedule",
        "overload",
        "syllabus",
        "backlog",
        "chapters",
        "many subjects",
        "handle all",
    ],
    "academic_confidence": [
        "hard",
        "difficult",
        "weak",
        "cannot understand",
        "low marks",
        "scores",
        "math",
        "physics",
        "chemistry",
        "bio",
    ],
    "social_comparison": [
        "compare",
        "topper",
        "better than me",
        "others",
        "rank",
        "friend scored",
        "competition",
    ],
    "family_pressure": ["family", "parents", "dad", "mom", "pressure", "scold"],
    "motivation": ["motivation", "dream", "goal", "want to", "demotivated", "lost"],
    "backlog_stress": ["backlog", "pending", "left", "incomplete", "syllabus left"],
}

COMBO_KEYWORDS = {
    "friend_compare_emotion": ["friend", "compare", "comparison", "distract"],
    "distraction_time_combo": ["gaming", "game", "time pressure", "timetable"],
}


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _has_denial(domain: str, text: str | None) -> bool:
    normalized = _norm(text)
    for pattern in DOMAIN_DENIAL_PATTERNS.get(domain, []):
        if re.search(pattern, normalized):
            return True
    return False


def _keyword_positive(text: str | None, keyword: str, window: int = 5) -> bool:
    normalized = _norm(text)
    escaped = re.escape(keyword.lower())
    for match in re.finditer(rf"\b{escaped}\b", normalized):
        left_context = normalized[max(0, match.start() - 80) : match.start()]
        left_words = left_context.split()
        near_left = left_words[-window:] if left_words else []
        if any(neg in " ".join(near_left) for neg in NEGATORS):
            continue
        return True
    return False


def _any_positive_keyword(text: str | None, keywords: Iterable[str]) -> bool:
    return any(_keyword_positive(text, keyword) for keyword in keywords)


def is_domain_relevant(
    domain: str,
    text: str,
    domain_keywords: dict[str, list[str]] | None = None,
) -> bool:
    keywords = domain_keywords or DOMAIN_KEYWORDS
    if _has_denial(domain, text):
        return False
    return _any_positive_keyword(text, keywords.get(domain, []))


def is_combo_relevant(
    combo_key: str,
    text: str,
    combo_keywords: dict[str, list[str]] | None = None,
) -> bool:
    keywords = combo_keywords or COMBO_KEYWORDS
    normalized_text = text or ""
    if combo_key == "friend_compare_emotion" and _has_denial("distractions", normalized_text):
        return False
    return _any_positive_keyword(normalized_text, keywords.get(combo_key, []))


def domain_relevant(domain: str, raw_text: str) -> bool:
    return is_domain_relevant(domain, raw_text, DOMAIN_KEYWORDS)


def combo_relevant(combo_key: str, raw_text: str) -> bool:
    return is_combo_relevant(combo_key, raw_text, COMBO_KEYWORDS)


__all__ = [
    "domain_relevant",
    "combo_relevant",
    "is_domain_relevant",
    "is_combo_relevant",
    "DOMAIN_KEYWORDS",
    "COMBO_KEYWORDS",
]
