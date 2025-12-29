"""Question generation via GPT with strict validation and fallbacks."""
from __future__ import annotations

import json
import logging

from .fallbacks import FALLBACK_QUESTIONS
from .validators import is_valid_question
from .openai_client import chat_json
from .generic_questions import get_generic_domain_question

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_QUESTION = """
You write ONE short, personalized follow-up question for an Indian JEE/NEET student.

Return STRICT JSON only:
{"question":"..."}

Rules:
- Output must be a single question ending with "?"
- No extra text. No numbering. No quotes outside JSON.
- Ask ONLY about the requested domain+slot.
- If stress_profile says a slot is negated (in __negated__), do NOT ask about it.
- Do not repeat the last question.
- Keep it simple English (no therapy tone).
"""



def generate_question(
    domain: str,
    slot: str,
    excerpt: str | None = None,
    context: dict | None = None,
) -> str | None:
    """Generate a slot-specific question with validation and fallback."""
    context = context or {}
    stress_profile = context.get("filled_slots") or {}
    negated_slots = []
    if isinstance(stress_profile.get("__negated__"), list):
        negated_slots = [slot for slot in stress_profile["__negated__"] if isinstance(slot, str)]
    meta = context.get("meta") or {}
    last_question = (meta.get("last_question") or "").strip()

    fallback = (FALLBACK_QUESTIONS.get(domain, {}) or {}).get(slot)
    if not fallback:
        fallback = "Can you share one quick detail about this?"

    payload = {
        "domain": domain,
        "slot": slot,
        "student_text": (context.get("user_text") or "")[:1200],
        "filled_slots": stress_profile,
        "negated_slots": negated_slots,
        "excerpt": excerpt or "",
        "last_question": last_question,
    }

    for attempt in (1, 2):
        question = ""
        try:
            resp = chat_json(
                model="gpt-5-mini",
                system=SYSTEM_PROMPT_QUESTION,
                user=json.dumps(payload, ensure_ascii=False),
            )
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            question = " ".join((data.get("question") or "").strip().split())
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("QUESTION_LLM_FAIL attempt=%s err=%s", attempt, exc)
            question = ""

        if question and question != last_question and is_valid_question(question):
            return question

        logger.warning("Invalid question (attempt %s): %s", attempt, question)

    return fallback


__all__ = ["generate_question", "get_generic_domain_question"]

