"""Slot utilities."""
from __future__ import annotations

from typing import Any

from ..constants import SLOT_SCHEMA
from .generic_questions import get_generic_slot_name


def ensure_domain_dict(filled_slots: dict, domain: str) -> dict:
    """Return a copy of the domain dict so reassignment marks JSON dirty."""
    domain_slots = filled_slots.get(domain)
    if not isinstance(domain_slots, dict):
        return {}
    return dict(domain_slots)


def is_slot_allowed(domain: str, slot: str) -> bool:
    if domain in SLOT_SCHEMA and slot in SLOT_SCHEMA[domain]:
        return True
    return slot == get_generic_slot_name(domain)


def get_slot_value(filled_slots: dict, domain: str, slot: str) -> Any:
    """Return stored slot value for convenience."""
    domain_data = filled_slots.get(domain, {})
    if not isinstance(domain_data, dict):
        return None
    return domain_data.get(slot)


def add_negated_slots(filled_slots: dict, slots: list[str]) -> None:
    if not slots:
        return
    existing = list(filled_slots.get("__negated__", []))
    for slot in slots:
        name = (slot or "").strip()
        if name and name not in existing:
            existing.append(name)
    if existing:
        filled_slots["__negated__"] = existing


def set_slot_value(filled_slots: dict, domain: str, slot: str, value: Any) -> None:
    if not is_slot_allowed(domain, slot):
        return
    domain_data = dict(filled_slots.get(domain, {}))
    domain_data[slot] = value
    filled_slots[domain] = domain_data


def is_slot_negated(filled_slots: dict, slot: str) -> bool:
    negated = filled_slots.get("__negated__", [])
    if not isinstance(negated, list):
        return False
    return slot in negated


def get_missing_slots(active_domains: list[str], filled_slots: dict) -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for domain in active_domains:
        for slot in SLOT_SCHEMA.get(domain, []):
            if filled_slots.get(domain, {}).get(slot) in (None, "", [], {}):
                missing.append((domain, slot))
    return missing


def infer_emotion_signals(filled_slots: dict) -> list[str]:
    """Derive emotion signals from stored slot values."""
    signals: set[str] = set()
    ac = filled_slots.get("academic_confidence") or {}
    exam_feeling = (ac.get("exam_feeling") or "").lower()
    concept = (ac.get("concept_confidence") or "").lower()

    if "low" in concept:
        signals.add("self_doubt")
    if "not made" in exam_feeling:
        signals.add("self_doubt")
    if "pressure" in exam_feeling:
        signals.add("pressure")

    mot = filled_slots.get("motivation") or {}
    demotivation = (mot.get("demotivation_reason") or "").lower()
    if "not made" in demotivation or "can't do" in demotivation:
        signals.add("panic")

    dis = filled_slots.get("distractions") or {}
    general_distraction = (dis.get("general_distraction") or "").lower()
    if "all day" in general_distraction or "whole day" in general_distraction:
        signals.add("distraction")

    return list(signals)


__all__ = [
    "ensure_domain_dict",
    "is_slot_allowed",
    "get_slot_value",
    "add_negated_slots",
    "set_slot_value",
    "is_slot_negated",
    "get_missing_slots",
    "infer_emotion_signals",
]
