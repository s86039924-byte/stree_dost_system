"""LLM guardrail for slot eligibility."""
from __future__ import annotations

import json
import logging

from .openai_client import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_SLOT_GATE = """
You decide whether a slot question should be asked.
Return STRICT JSON only:
{"ask": true | false}

Rules:
- If the user clearly denies a cause, return ask=false for those slots.
- Do not invent or explain. Only rely on the provided user_text.
- Be conservative: if unsure, set ask=false.
"""


def should_ask_slot(user_text: str, domain: str, slot: str) -> bool:
    payload = {
        "user_text": (user_text or "")[:2000],
        "domain": domain,
        "slot": slot,
    }
    try:
        resp = chat_json(
            model="gpt-5-mini",
            system=SYSTEM_PROMPT_SLOT_GATE,
            user=json.dumps(payload, ensure_ascii=False),
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        return bool(data.get("ask", False))
    except Exception as exc:  # pragma: no cover - fail open
        logger.warning("slot gate failed for %s.%s: %s", domain, slot, exc)
        return True


__all__ = ["should_ask_slot"]
