"""Generate stress popups via GPT with strict validation."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from .popup_schemas import Popup
from .popup_validator import validate_popup_message
from .openai_client import chat_json

logger = logging.getLogger(__name__)

FALLBACK_TEMPLATES = {
    "pressure": "Schedule feels crushing right now 😔\nSlow inhale, slow exhale, one step at a time.",
    "self_doubt": "Mind says you aren't prepared enough.\nCounter it: you have survived tougher days.",
    "panic": "Heart racing like the bell already rang.\nCount 5-4-3-2-1, eyes back to the sheet.",
    "motivation": "Dream college still needs your fight.\nTiny effort now beats big regret later.",
    "distraction": "Phone gossip will still be there later.\nGive me 10 focused mins, then check it.",
}


def _fallback_sequence(emotion_signals: list[str] | None) -> list[str]:
    ordered: list[str] = []
    for signal in emotion_signals or []:
        if signal in FALLBACK_TEMPLATES and signal not in ordered:
            ordered.append(signal)
    for default in ["pressure", "self_doubt", "panic", "motivation", "distraction"]:
        if default in FALLBACK_TEMPLATES and default not in ordered:
            ordered.append(default)
    return ordered


def _fallback_popups(
    count: int,
    seen: set[tuple[str, str]],
    emotion_signals: list[str],
) -> list[dict]:
    created: list[dict] = []
    for popup_type in _fallback_sequence(emotion_signals):
        if len(created) >= count:
            break
        message = FALLBACK_TEMPLATES.get(popup_type)
        if not message:
            continue
        key = (popup_type, message.strip())
        if key in seen:
            continue
        lines = [ln.strip() for ln in message.split("\n") if ln.strip()]
        for line in lines or [message]:
            sub_key = (popup_type, line)
            if sub_key in seen:
                continue
            payload = {
                "type": popup_type,
                "message": line,
                "ttl": 12000,
            }
            created.append(payload)
            seen.add(sub_key)
    return created


def _ensure_minimum_popups(
    popups: list[dict],
    seen: set[tuple[str, str]],
    emotion_signals: list[str],
    minimum: int = 3,
    limit: int = 15,
) -> list[dict]:
    augmented = list(popups)
    if len(augmented) < minimum:
        needed = minimum - len(augmented)
        augmented.extend(_fallback_popups(needed, seen, emotion_signals))
    return augmented[:limit]


def _explode_popup(validated: Popup) -> list[dict]:
    """Split multi-line messages into individual popup cards."""
    lines = [ln.strip() for ln in (validated.message or "").split("\n") if ln.strip()]
    base = {
        "type": validated.type,
        "ttl": validated.ttl,
    }
    if len(lines) <= 1:
        payload = base | {"message": validated.message.strip()}
        return [payload]

    exploded: list[dict] = []
    for line in lines:
        exploded.append(base | {"message": line})
    return exploded

SYSTEM_PROMPT_POPUPS = """
You generate intrusive, exam-stress pop-ups during a test for Indian JEE/NEET students.

Return STRICT JSON only:
{"popups":[{"type":"distraction","message":"...","ttl":8000}]}

Allowed types ONLY:
distraction, self_doubt, panic, pressure, motivation, parental_pressure, fear, doubt, girlfriend, stress, anxiety

Hard limits:
- Generate EXACTLY 12 popups.
- message must be EXACTLY 2 lines using \\n.
- Total message length <= 180 characters.
- Each line <= 90 characters.
- Use simple English; Hindi/Hinglish is allowed when it adds flavor.
- Use 1 or 2 sarcastic emoji based on test you will generate (at end of line 1 or line 2).
- Do NOT repeat the same message.

Tone rules (IMPORTANT):
- Sound like a bully guy who makes fun of the student speak like hit hard to student(use hindi language words where possible).
- Can be sarcastic or sharp, insult the student and call them stupid, lazy, useless, hopeless, idiot, loser.
- wish failure, ranks and  humiliation. Do personal attacks based on stress_profile.
- be hatefull for student by mocking their weaknesses and failures.
- Use humor, sarcasm, and exaggeration to create a sense of urgency and stress about the exam.
- Reference common Indian JEE/NEET exam stressors (time pressure, tough questions, distractions, parental expectations).
- Use rhetorical questions to provoke anxiety (e.g., "Can't you even answer this simple question?").
- Do NOT ask therapy questions. No advice paragraphs or motivational speeches - Be direct and to the point, no fluff.

Personalization:
- Use given stress_profile (paraphrase lightly) and craete senario that mock and insult and then generate pop ups based on that.
- If weak_subject exists, insult the student's ability in that subject.
- If coaching is mentioned as bad, reflect "unfair disadvantage / frustration" (mock the student).

- If weak_subject exists, reference that subject in a dramatic exam-thought way like "Maybe if you had studied {weak_subject}, you wouldn't be in this mess!", "Another {weak_subject} question, surprise surprise!", "Your {weak_subject} skills are as useless as your exam strategy.", "Struggling with {weak_subject} again? Shocking, just shocking.does {weak subject concept} make you cry {laughing emoji}".


Chat-style optional (if data dont exixt still mock the student and insult him):
- If family_member mentions mom/mother/dad/father/brother/parents/family:
  you MAY format: "Mom: ...\\n..."
- If friend_name or comparison_person exists:
  use "<Name>:"; if generic ("friends") use "Friend:".

TTL:
- ttl between 6000 and 9000.
"""



def normalize_two_lines(msg: str, max_total: int = 160, max_line: int = 80) -> str:
    msg = (msg or "").strip()
    lines = [ln.strip() for ln in msg.split("\n") if ln.strip()]

    if len(lines) < 2:
        cleaned = msg.replace("?", ".").replace("!", ".")
        parts = [p.strip() for p in cleaned.split(".") if p.strip()]
        if len(parts) >= 2:
            lines = [parts[0], parts[1]]
        else:
            words = msg.split()
            if len(words) >= 6:
                mid = max(3, min(len(words) // 2, len(words) - 3))
                lines = [" ".join(words[:mid]), " ".join(words[mid:])]
            else:
                lines = [msg, msg]

    line1, line2 = lines[0], lines[1]
    line1 = line1[:max_line].rstrip()
    line2 = line2[:max_line].rstrip()

    joined = f"{line1}\n{line2}"
    if len(joined) > max_total:
        overflow = len(joined) - max_total
        if overflow > 0:
            line2 = line2[: max(0, len(line2) - overflow)].rstrip()
        joined = f"{line1}\n{line2}"
        if len(joined) > max_total:
            overflow = len(joined) - max_total
            line1 = line1[: max(0, len(line1) - overflow)].rstrip()
            joined = f"{line1}\n{line2}"

    return joined


def generate_popups(stress_profile: dict, emotion_signals: list[str] | None = None) -> list[dict]:
    if not stress_profile:
        return []

    payload = {
        "stress_profile": stress_profile,
        "emotion_signals": emotion_signals or [],
    }

    for attempt in (1, 2):
        try:
            response = chat_json(
                model="gpt-5-mini",
                system=SYSTEM_PROMPT_POPUPS,
                user=json.dumps(payload, ensure_ascii=False),
            )

            raw = (response.choices[0].message.content or "").strip()
            logger.info("POPUP_RAW attempt=%s raw=%s", attempt, raw)

            data = json.loads(raw)
            popups = data.get("popups") or []

            valid_popups: list[dict] = []
            seen: set[tuple[str, str]] = set()

            for popup in popups:
                if not isinstance(popup, dict):
                    continue
                popup["message"] = normalize_two_lines(popup.get("message", ""))
                popup["ttl"] = int(popup.get("ttl", 12000))
                popup["ttl"] = max(10000, min(14000, popup["ttl"]))

                try:
                    validated = Popup.model_validate(popup)
                except ValidationError as e:
                    logger.warning("POPUP_SCHEMA_FAIL popup=%s err=%s", popup, e)
                    continue

                if validate_popup_message(validated.message, stress_profile):
                    for sub in _explode_popup(validated):
                        key = (sub["type"], sub["message"].strip())
                        if key in seen:
                            continue
                        seen.add(key)
                        valid_popups.append(sub)

            if valid_popups:
                augmented = _ensure_minimum_popups(
                    valid_popups,
                    seen,
                    emotion_signals or [],
                )
                logger.info("POPUP_OK count=%s", len(augmented))
                return augmented

            logger.warning("POPUP_EMPTY_AFTER_VALIDATION attempt=%s", attempt)

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error("POPUP_PARSE_FAIL attempt=%s err=%s", attempt, exc)

        except Exception as exc:
            logger.exception("POPUP_CALL_FAIL attempt=%s err=%s", attempt, exc)
            break

    fallback = _fallback_popups(3, set(), emotion_signals or [])
    if fallback:
        return fallback[:15]

    return []



__all__ = ["generate_popups"]
