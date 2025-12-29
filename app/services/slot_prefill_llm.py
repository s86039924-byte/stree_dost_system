"""LLM-powered slot prefilling."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from ..constants import SLOT_SCHEMA
from .slot_prefill_schema import SlotPrefillResponse
from .openai_client import chat_json

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_PREFILL = """
You are a slot extractor for a student stress-test system.

Return ONLY JSON (no markdown). Use the provided SLOT_SCHEMA.
Rules:
- Only use domains and slots that exist in SLOT_SCHEMA.
- If a value is not clearly stated/implied, do not guess.
- Values should be short (1–8 words). No long sentences.
- You may correct spelling/casing (e.g., "instragram" -> "Instagram").
- active_domains should include the stress domains present in the user's text.
- If the user explicitly says a slot does NOT apply (e.g., "not distracted by phone"),
  add that slot name to negated_slots.

Output format:
{
  "active_domains": ["distractions", "time_pressure"],
  "negated_slots": ["phone_app"],
  "prefill": {
    "distractions": {"phone_app": "Instagram"}
  }
}
"""


def prefill_slots_with_llm(user_text: str) -> SlotPrefillResponse:
    """Infer domains and slot prefills from the initial user text."""
    if not (user_text or "").strip():
        return SlotPrefillResponse(active_domains=[], prefill={})

    payload = {
        "SLOT_SCHEMA": SLOT_SCHEMA,
        "user_text": user_text[:2000],
    }

    for attempt in (1, 2):
        try:
            resp = chat_json(
                model="gpt-5-mini",
                system=SYSTEM_PROMPT_PREFILL,
                user=json.dumps(payload, ensure_ascii=False),
            )
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            parsed = SlotPrefillResponse(**data)

            clean_prefill: dict[str, dict[str, str]] = {}
            negated_slots: list[str] = []
            for domain, slots in (parsed.prefill or {}).items():
                if domain not in SLOT_SCHEMA or not isinstance(slots, dict):
                    continue
                for slot, value in slots.items():
                    if (
                        slot in SLOT_SCHEMA[domain]
                        and isinstance(value, str)
                        and value.strip()
                    ):
                        clean_prefill.setdefault(domain, {})[slot] = (
                            " ".join(value.strip().split())[:80]
                        )

            for slot in parsed.negated_slots or []:
                slot_name = (slot or "").strip()
                if not slot_name:
                    continue
                if any(slot_name in SLOT_SCHEMA[d] for d in SLOT_SCHEMA):
                    negated_slots.append(slot_name)

            return SlotPrefillResponse(
                active_domains=parsed.active_domains or [],
                prefill=clean_prefill,
                negated_slots=negated_slots,
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("prefill_slots_with_llm attempt %s failed: %s", attempt, exc)
        except Exception as exc:  # pragma: no cover
            logger.exception("prefill_slots_with_llm error: %s", exc)
            break

    return SlotPrefillResponse(active_domains=[], prefill={})


__all__ = ["prefill_slots_with_llm"]
