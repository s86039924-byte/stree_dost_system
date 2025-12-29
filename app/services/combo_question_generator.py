"""Combined question generation."""
from __future__ import annotations

from .combo_specs import COMBO_SPECS, FORBIDDEN_COMBOS
from .slot_manager import get_slot_value


def _missing_slots(session, slots: list[tuple[str, str]]) -> list[tuple[str, str]]:
    missing = []
    filled = session.filled_slots or {}
    for domain, slot in slots:
        value = get_slot_value(filled, domain, slot)
        if value is None:
            missing.append((domain, slot))
        elif isinstance(value, str) and not value.strip():
            missing.append((domain, slot))
    return missing


def _combo_categories(spec: dict) -> set[str]:
    categories: set[str] = set()
    for domain, _ in spec.get("slots") or []:
        if domain == "distractions":
            categories.add("distraction")
        if domain == "social_comparison":
            categories.add("comparison")
    if spec.get("emotion_probe"):
        categories.add("emotion")
    return categories


def generate_combo_question(combo_key: str, session, user_text: str | None = None) -> str | None:
    """Return a combo question that only asks for missing pieces."""
    spec = COMBO_SPECS.get(combo_key)
    if not spec:
        return None

    categories = _combo_categories(spec)
    for forbidden in FORBIDDEN_COMBOS:
        if forbidden.issubset(categories):
            return None

    slots = spec.get("slots") or []
    missing = _missing_slots(session, slots)
    if not missing:
        return None

    if len(missing) == 1:
        domain, slot = missing[0]
        if (domain, slot) == ("distractions", "friend_name"):
            return "Which friend distracts you the most (if any)?"
        if (domain, slot) == ("social_comparison", "comparison_person"):
            return "Who do you usually compare yourself with (if you do compare)?"
        if (domain, slot) == ("social_comparison", "comparison_gap"):
            return "When you compare, does the gap feel small or big?"
        return "Can you share one short detail about that?"

    prompts: list[str] = []
    for domain, slot in missing:
        if (domain, slot) == ("distractions", "friend_name"):
            prompts.append("1) Friend who distracts you most (or say 'none')")
        elif (domain, slot) == ("social_comparison", "comparison_person"):
            prompts.append("2) Person you compare yourself to (or say 'no one')")
        elif (domain, slot) == ("social_comparison", "comparison_gap"):
            prompts.append("3) Gap feels small or big")
        else:
            prompts.append(f"- {domain}.{slot}")

    if spec.get("emotion_probe"):
        prompts.append("4) Emotion right now: pressure / panic / self_doubt / motivation")

    return "Quick check so I can personalize things:\n" + "\n".join(prompts)


__all__ = ["generate_combo_question"]
