"""Domain fatigue planner."""
from __future__ import annotations

from ..constants import PRIORITY_ORDER
from .slot_gate_llm import should_ask_slot
from .generic_questions import get_generic_slot_name

DOMAIN_CAUSE_MAP = {
    "family_pressure": ["family_pressure"],
    "distractions": ["digital_distraction"],
    "social_comparison": ["social_distraction"],
    "academic_confidence": ["academic_confidence"],
    "time_pressure": ["time_pressure"],
}


def activate_domains_from_causes(causes: dict[str, bool]) -> list[str]:
    causes = causes or {}
    active: list[str] = []
    for domain in PRIORITY_ORDER:
        if is_domain_allowed_by_cause(domain, causes):
            active.append(domain)
    return active


def is_domain_allowed_by_cause(domain: str, causes: dict[str, bool]) -> bool:
    keys = DOMAIN_CAUSE_MAP.get(domain)
    if not keys:
        return False
    return any(bool(causes.get(key)) for key in keys)


def is_slot_allowed_by_cause(domain: str, causes: dict[str, bool]) -> bool:
    return is_domain_allowed_by_cause(domain, causes)


def pick_next_slot(
    active_domains: list[str],
    missing_slots: list[tuple[str, str]],
    domain_question_count: dict,
    max_domain_questions: int,
    user_text: str,
    filled_slots: dict,
    causes: dict[str, bool] | None,
) -> tuple[str, str] | None:

    slots_by_domain: dict[str, list[tuple[str, str]]] = {}
    for domain, slot in missing_slots:
        slots_by_domain.setdefault(domain, []).append((domain, slot))

    negated = set()
    if isinstance(filled_slots.get("__negated__"), list):
        negated = set(filled_slots["__negated__"])

    gate_cache: dict[tuple[str, str], bool] = {}
    causes = causes or {}

    def _eligible(domain: str, slot: str) -> bool:
        if slot in negated:
            return False
        if not is_slot_allowed_by_cause(domain, causes):
            return False
        key = (domain, slot)
        if key not in gate_cache:
            gate_cache[key] = should_ask_slot(user_text, domain, slot)
        return gate_cache[key]

    for domain in PRIORITY_ORDER:
        if domain not in active_domains:
            continue
        if domain_question_count.get(domain, 0) >= max_domain_questions:
            continue
        for _, slot in slots_by_domain.get(domain, []):
            if _eligible(domain, slot):
                return (domain, slot)

    for domain, slot in missing_slots:
        if domain_question_count.get(domain, 0) >= max_domain_questions:
            continue
        if _eligible(domain, slot):
            return (domain, slot)

    for domain in active_domains:
        if domain_question_count.get(domain, 0) >= max_domain_questions:
            continue
        if not is_domain_allowed_by_cause(domain, causes):
            continue
        generic_slot = get_generic_slot_name(domain)
        if not generic_slot:
            continue
        existing = filled_slots.get(domain, {}).get(generic_slot)
        if existing:
            continue
        return (domain, "__generic__")

    return None


__all__ = [
    "pick_next_slot",
    "activate_domains_from_causes",
    "DOMAIN_CAUSE_MAP",
    "is_slot_allowed_by_cause",
    "is_domain_allowed_by_cause",
]
