"""GPT helper utilities for domain extraction."""
from __future__ import annotations

import json
import logging
from typing import Dict, List

from pydantic import ValidationError

from .schemas import ExtractComponentsResponse
from .openai_client import chat_json, chat_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_EXTRACT = """
You extract stress components from student text.

Return STRICT JSON only. No markdown. No extra keys.
Allowed ids only:
academic_confidence, time_pressure, distractions, social_comparison, family_pressure, motivation, demotivation, backlog_stress

Output format exactly:
{"components":[{"id":"time_pressure","excerpt":"..." }]}
"""

CAUSE_KEYS = [
    "family_pressure",
    "digital_distraction",
    "social_distraction",
    "academic_confidence",
    "time_pressure",
    "emotional_overwhelm",
]

SYSTEM_PROMPT_CAUSES = """
Given the user text, detect ONLY the causes they explicitly mention.

Allowed causes:
- family_pressure
- digital_distraction
- social_distraction
- academic_confidence
- time_pressure
- emotional_overwhelm

Rules:
- If the user explicitly denies a cause, return false for it.
- Do NOT infer or guess causes that were not clearly stated.
- Return STRICT JSON only with boolean values per cause.
"""


def extract_components(text: str) -> List[str]:
    """
    Returns a deduped list of component ids.
    Validation: strict JSON + Pydantic schema.
    Regenerate once on failure, then fallback keywords.
    """
    user_text = (text or "").strip()
    if not user_text:
        return []

    for attempt in (1, 2):
        try:
            response = chat_text(
                model="gpt-5-mini",
                system=SYSTEM_PROMPT_EXTRACT,
                user=user_text[:1500],
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            parsed = ExtractComponentsResponse(**data)

            seen = set()
            ordered = []
            for component in parsed.components:
                if component.id not in seen:
                    seen.add(component.id)
                    ordered.append(component.id)
            return filter_domains_by_denials(ordered, text)

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("extract_components attempt %s failed: %s", attempt, exc)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("extract_components unexpected error: %s", exc)
            break

    return keyword_fallback(user_text)


def keyword_fallback(text: str) -> List[str]:
    lowered = text.lower()
    out: List[str] = []

    def add(component: str) -> None:
        if component not in out:
            out.append(component)

    if any(token in lowered for token in ["time", "deadline", "weeks", "days", "exam", "test in", "paper in"]):
        add("time_pressure")
    if any(token in lowered for token in ["phone", "instagram", "youtube", "snapchat", "reel", "shorts", "game", "bgmi", "freefire"]):
        add("distractions")
    if any(token in lowered for token in ["math", "physics", "chemistry", "bio", "marks", "score", "rank", "concepts"]):
        add("academic_confidence")
    if any(token in lowered for token in ["compare", "topper", "better than me", "friends ahead", "sharma ji"]):
        add("social_comparison")
    if any(token in lowered for token in ["mom", "dad", "parents", "family", "ghar", "pressure"]):
        add("family_pressure")
    if any(token in lowered for token in ["motivation", "dream", "goal", "iit", "aiims"]):
        add("motivation")
    if any(token in lowered for token in ["demotivat", "tired", "burnout", "give up", "hopeless"]):
        add("demotivation")
    if any(token in lowered for token in ["backlog", "syllabus left", "pending chapters"]):
        add("backlog_stress")

    return filter_domains_by_denials(out, text)


def filter_domains_by_denials(active_domains: List[str], initial_text: str | None) -> List[str]:
    text = (initial_text or "").lower()
    filtered = list(active_domains)
    def _remove(domain: str) -> None:
        nonlocal filtered
        filtered = [d for d in filtered if d != domain]

    if any(
        phrase in text
        for phrase in [
            "not distracted by phone",
            "not distracted by my phone",
            "not distracted by friends",
            "no phone distraction",
            "no distractions from friends",
        ]
    ):
        _remove("distractions")
    if any(
        phrase in text
        for phrase in [
            "dont compare",
            "don't compare",
            "do not compare",
            "i am not comparing",
        ]
    ):
        _remove("social_comparison")
    return filtered


def detect_causes(user_text: str) -> Dict[str, bool]:
    """Return boolean cause map using constrained GPT output."""
    payload = {"user_text": (user_text or "")[:2000]}
    default = {key: False for key in CAUSE_KEYS}
    if not payload["user_text"]:
        return default

    for attempt in (1, 2):
        try:
            resp = chat_json(
                model="gpt-5-mini",
                system=SYSTEM_PROMPT_CAUSES,
                user=json.dumps(payload, ensure_ascii=False),
            )
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            result = default.copy()
            for key in CAUSE_KEYS:
                if isinstance(data.get(key), bool):
                    result[key] = data[key]
            return result
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("detect_causes attempt %s failed: %s", attempt, exc)
        except Exception as exc:  # pragma: no cover
            logger.exception("detect_causes unexpected error: %s", exc)
            break
    return default


__all__ = ["extract_components", "keyword_fallback", "detect_causes"]
