"""LLM-powered question mutation for stress/distraction scenarios."""
from __future__ import annotations

import json
import logging
import re
from typing import Tuple

from .openai_client import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_MUTATE = """
You mutate a single exam question by changing numeric values and recomputing the correct answer.

Supported types:
- scq (single correct option, labels A-D)
- integer (single integer answer)

Return STRICT JSON only:
{"question_html":"...","options":[{"label":"A","text":"..."}],"correct_answer":"A","solution_html":"...","integer_answer": null}

Rules:
- Change numeric values (magnitudes/constants) but keep topic and structure.
- For scq: keep labels the same; set correct_answer to the new correct label; ensure exactly one correct option.
- For integer: options must be an empty list; set integer_answer to the new correct integer.
- Preserve HTML tags already used (<p>, <br>, <b>, <i>); do NOT add images, tables, or LaTeX.
- Keep wording concise; do not add instructions/hints.
- If mutation is unsafe, return the original fields unchanged.
"""


def _safe_options(options):
    if not isinstance(options, list):
        return None
    cleaned = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        label = (opt.get("label") or "").strip()[:5]
        text = " ".join((opt.get("text") or "").strip().split())[:300]
        if label and text:
            cleaned.append({"label": label, "text": text})
    return cleaned or None


def _nudge_first_number(text: str) -> tuple[str, bool, float | None]:
    """Replace the first numeric literal by incrementing it. Returns (text, changed, delta)."""
    if not isinstance(text, str):
        return text, False, None
    match = re.search(r"(?P<num>\\d+(?:\\.\\d+)?)", text)
    if not match:
        return text, False, None
    original = match.group("num")
    delta: float
    nudged: str
    if "." in original:
        try:
            old_val = float(original)
            new_val = old_val + 1
            delta = new_val - old_val
            nudged = f"{new_val:.2f}".rstrip("0").rstrip(".")
        except Exception:
            return text, False, None
    else:
        try:
            old_val = int(original)
            new_val = old_val + 1
            delta = float(new_val - old_val)
            nudged = str(new_val)
        except Exception:
            return text, False, None
    start, end = match.span("num")
    return text[:start] + nudged + text[end:], True, delta


def _deterministic_nudge(question: dict) -> tuple[dict, bool]:
    """Fallback deterministic mutation to ensure visible change when LLM keeps original."""
    qtype = (question.get("question_type") or "").lower()
    mutated = dict(question)
    changed = False

    if qtype == "integer":
        html, nudged, delta = _nudge_first_number(mutated.get("question_html") or "")
        if nudged:
            mutated["question_html"] = html
            changed = True
            try:
                base_ans = mutated.get("integer_answer")
                if base_ans is not None and delta is not None:
                    base_val = float(base_ans)
                    new_val = base_val + delta
                    if abs(new_val - round(new_val)) < 1e-6:
                        mutated["integer_answer"] = int(round(new_val))
                    else:
                        mutated["integer_answer"] = new_val
            except Exception:
                pass
        mutated["options"] = []

    elif qtype == "scq":
        html, nudged, _ = _nudge_first_number(mutated.get("question_html") or "")
        if nudged:
            mutated["question_html"] = html
            changed = True
        new_opts: list[dict] = []
        for opt in mutated.get("options") or []:
            if not isinstance(opt, dict):
                continue
            text, opt_nudged, _ = _nudge_first_number(opt.get("text") or "")
            if opt_nudged:
                changed = True
            new_opts.append({"label": opt.get("label"), "text": text})
        if new_opts:
            mutated["options"] = new_opts

    return mutated, changed


def mutate_question(question: dict) -> Tuple[dict, bool]:
    """
    Return (mutated_question, mutated_flag).
    Only scq and integer questions are mutated; others are returned as-is.
    """
    qtype = (question.get("question_type") or "").lower()
    if qtype not in {"scq", "integer"}:
        return question, False

    base_payload = {
        "question_type": qtype,
        "question_html": question.get("question_html") or "",
        "options": question.get("options") or [],
        "correct_answer": question.get("correct_answer"),
        "integer_answer": question.get("integer_answer"),
        "solution_html": question.get("solution_html") or "",
    }

    try:
        resp = chat_json(
            model="gpt-5-mini",
            system=SYSTEM_PROMPT_MUTATE,
            user=json.dumps(base_payload, ensure_ascii=False),
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("question mutate failed: %s", exc)
        return question, False

    mutated = dict(question)
    mutated["question_html"] = data.get("question_html") or mutated.get("question_html") or ""
    mutated["solution_html"] = data.get("solution_html") or mutated.get("solution_html") or ""

    if qtype == "scq":
        new_opts = _safe_options(data.get("options"))
        if new_opts:
            mutated["options"] = new_opts
        new_answer = (data.get("correct_answer") or "").strip()
        labels = {opt.get("label") for opt in mutated.get("options", []) if isinstance(opt, dict)}
        if new_answer and new_answer in labels:
            mutated["correct_answer"] = new_answer
    elif qtype == "integer":
        mutated["options"] = []
        try:
            if data.get("integer_answer") is not None:
                mutated["integer_answer"] = int(data.get("integer_answer"))
        except Exception:
            pass

    changed = json.dumps(mutated, sort_keys=True) != json.dumps(question, sort_keys=True)

    # Deterministic nudge if LLM kept the original
    if not changed:
        nudged, nudged_changed = _deterministic_nudge(question)
        if nudged_changed:
            mutated = nudged
            changed = True
            logger.info("question_mutated type=%s mutated=True (deterministic_nudge)", qtype)

    if changed:
        logger.info("question_mutated type=%s mutated=True", qtype)
    else:
        logger.info("question_mutated type=%s mutated=False (fallback to original)", qtype)
    return mutated, changed


__all__ = ["mutate_question"]
