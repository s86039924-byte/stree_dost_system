"""Session routes."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..db.repo import create_session, get_session, save_session
from ..extensions import socketio
from ..realtime.scheduler import start_popup_simulation
from ..services.combo_answer_parser import PARSERS as COMBO_PARSERS
from ..services.combo_question_generator import generate_combo_question
from ..services.combo_specs import COMBO_SPECS
from ..services.fallbacks import CLARIFIER_QUESTION
from ..services.gpt_client import detect_causes
from ..services.planner import (
    activate_domains_from_causes,
    pick_next_slot,
)
from ..services.popup_generator import generate_popups
from ..services.question_generator import generate_question, get_generic_domain_question
from ..services.slot_manager import (
    add_negated_slots,
    get_missing_slots,
    infer_emotion_signals,
    is_slot_allowed,
    set_slot_value,
)
from ..services.slot_prefill_llm import prefill_slots_with_llm
from ..services.relevance import combo_relevant, domain_relevant
from ..services.stop_engine import should_stop

bp = Blueprint("session", __name__, url_prefix="/session")


@bp.post("/start")
def start_session():
    body = request.get_json(force=True, silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    session = create_session(text)

    prefill = prefill_slots_with_llm(text)

    causes = detect_causes(text)
    meta = dict(session.meta or {})
    meta["causes"] = causes
    session.meta = meta

    session.active_domains = prefill.active_domains or activate_domains_from_causes(causes)

    for domain, slots in (prefill.prefill or {}).items():
        for slot, value in slots.items():
            set_slot_value(session.filled_slots, domain, slot, value)
    add_negated_slots(session.filled_slots, prefill.negated_slots or [])

    if not session.active_domains:
        session.active_domains = ["time_pressure", "distractions", "academic_confidence"]

    save_session(session)

    return jsonify(
        {
            "session_id": str(session.id),
            "status": session.status,
            "active_domains": session.active_domains,
            "prefilled": session.filled_slots,
        }
    )


@bp.post("/<session_id>/answer")
def answer(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404
    if session.status != "active":
        return jsonify({"error": "session is not active"}), 400

    body = request.get_json(force=True, silent=True) or {}
    answer_text = (body.get("answer") or "").strip()

    meta = dict(session.meta or {})
    current_question = meta.get("current_question") or {}
    if current_question.get("type") == "combo":
        combo_id = current_question.get("combo_id")
        parser = COMBO_PARSERS.get(combo_id)
        if parser:
            parsed = parser(answer_text)
            if not parsed:
                hint = COMBO_SPECS.get(combo_id, {}).get("hint", "")
                return jsonify(
                    {
                        "need_clarification": True,
                        "question": f"Please follow the format:\n{hint}",
                    }
                )

            for key, value in parsed["slots"].items():
                domain_key, slot_key = key.split(".", 1)
                set_slot_value(session.filled_slots, domain_key, slot_key, value)

            emotion = parsed.get("emotion")
            if emotion:
                signals = list(meta.get("emotion_signals") or [])
                signals.append(emotion)
                meta["emotion_signals"] = signals

            meta["current_question"] = None
            session.meta = meta
            session.history.append({"role": "user", "text": answer_text})
            save_session(session)
            return jsonify({"ok": True, "filled_slots": session.filled_slots, "meta": session.meta})

    domain = body.get("domain")
    slot = body.get("slot")
    domain = domain or current_question.get("domain")
    slot = slot or current_question.get("slot")

    if not (domain and slot):
        return jsonify({"error": "domain/slot missing (no current_question found)"}), 400

    if not is_slot_allowed(domain, slot):
        return jsonify({"error": "invalid domain/slot"}), 400

    if not answer_text:
        return jsonify({"error": "answer is required"}), 400

    clarifier_used = list(meta.get("clarifier_used") or [])
    key = f"{domain}.{slot}"
    if len(answer_text.split()) < 2 and key not in clarifier_used:
        clarifier_used.append(key)
        meta["clarifier_used"] = clarifier_used
        meta["current_question"] = {
            "domain": domain,
            "slot": slot,
            "question": CLARIFIER_QUESTION,
        }
        session.meta = meta

        session.history.append({"role": "user", "text": answer_text})
        session.history.append({"role": "assistant", "text": CLARIFIER_QUESTION})
        save_session(session)
        return jsonify(
            {
                "need_clarification": True,
                "domain": domain,
                "slot": slot,
                "question": CLARIFIER_QUESTION,
            }
        )

    session.history.append({"role": "user", "text": answer_text})
    set_slot_value(session.filled_slots, domain, slot, answer_text)
    meta["current_question"] = None
    session.meta = meta

    save_session(session)
    return jsonify({"ok": True, "filled_slots": session.filled_slots, "meta": session.meta})


@bp.post("/<session_id>/next-question")
def next_question(session_id: str):
    session = get_session(session_id)
    if not session or session.status != "active":
        return jsonify({"error": "invalid session"}), 400

    current_q = (session.meta or {}).get("current_question")
    if current_q:
        return jsonify(
            {
                "done": False,
                "domain": current_q.get("domain"),
                "slot": current_q.get("slot"),
                "question": current_q.get("question"),
                "meta": session.meta,
                "pending": True,
                "message": "Answer the current question first",
            }
        )

    if not session.active_domains:
        session.active_domains = extract_components(session.raw_initial_text or "")

    if not session.active_domains:
        causes = meta.get("causes")
        if not causes:
            causes = detect_causes(session.raw_initial_text or "")
            meta["causes"] = causes
            session.meta = meta
        session.active_domains = activate_domains_from_causes(causes)

    if not session.active_domains:
        session.active_domains = ["time_pressure", "distractions", "academic_confidence"]

    missing = get_missing_slots(session.active_domains, session.filled_slots)

    def _is_missing(domain: str, slot: str) -> bool:
        return not session.filled_slots.get(domain, {}).get(slot)

    meta = dict(session.meta or {})
    total_questions = int(meta.get("total_questions_asked", 0))
    domain_counts = dict(meta.get("domain_question_count") or {})
    combo_history = set(meta.get("combo_history") or [])
    raw_text = session.raw_initial_text or ""

    combo_spec_id = None
    combo_spec = None

    if total_questions <= 2:
        if (
            "friend_compare_emotion" not in combo_history
            and combo_relevant("friend_compare_emotion", raw_text)
            and domain_relevant("social_comparison", raw_text)
            and (
                _is_missing("distractions", "friend_name")
                or _is_missing("social_comparison", "comparison_person")
                or _is_missing("social_comparison", "comparison_gap")
            )
        ):
            combo_spec_id = "friend_compare_emotion"
        elif (
            "distraction_time_combo" not in combo_history
            and combo_relevant("distraction_time_combo", raw_text)
            and domain_relevant("distractions", raw_text)
            and domain_relevant("time_pressure", raw_text)
            and (
                _is_missing("distractions", "gaming_app")
                or _is_missing("distractions", "gaming_time")
                or _is_missing("time_pressure", "timetable_breaker")
            )
        ):
            combo_spec_id = "distraction_time_combo"

    if combo_spec_id:
        combo_spec = COMBO_SPECS[combo_spec_id]
        question = generate_combo_question(combo_spec_id, session, session.raw_initial_text or "")
    if combo_spec_id and combo_spec and question:
        meta["total_questions_asked"] = total_questions + 1
        meta["current_question"] = {
            "type": "combo",
            "combo_id": combo_spec_id,
            "question": question,
        }
        history = list(combo_history)
        history.append(combo_spec_id)
        meta["combo_history"] = history
        session.meta = meta
        session.history.append({"role": "assistant", "text": question})
        save_session(session)
        return jsonify(
            {
                "done": False,
                "combo": True,
                "question": question,
                "hint": combo_spec["hint"],
                "meta": session.meta,
            }
        )
    elif combo_spec_id and not question:
        combo_spec_id = None

    if should_stop(
        total_questions_asked=total_questions,
        missing_slots_count=len(missing),
        min_questions=current_app.config["MIN_QUESTIONS"],
        max_questions=current_app.config["MAX_QUESTIONS"],
    ):
        return _complete_session(session)

    question = None
    domain = slot = None
    attempts = 0
    max_attempts = len(missing) + 3

    while attempts < max_attempts:
        missing = get_missing_slots(session.active_domains, session.filled_slots)
        next_slot = pick_next_slot(
            session.active_domains,
            missing,
            domain_counts,
            current_app.config["MAX_DOMAIN_QUESTIONS"],
            session.raw_initial_text or "",
            session.filled_slots,
            meta.get("causes") or {},
        )
        if not next_slot:
            return _complete_session(session)

        domain, slot = next_slot
        profile = session.filled_slots or {}
        domain_profile = profile.get(domain) or {}

        excerpt = None
        if domain == "academic_confidence":
            weak = domain_profile.get("weak_subject") or ""
            last = domain_profile.get("last_test_experience") or ""
            if weak or last:
                excerpt = f"Weak in {weak}. Last test felt {last}."
        elif domain == "family_pressure":
            expect = domain_profile.get("expectation_type") or ""
            member = domain_profile.get("family_member") or ""
            if expect or member:
                excerpt = f"Family member {member} expects {expect}."
        elif domain == "distractions":
            friend = domain_profile.get("friend_name") or ""
            app = domain_profile.get("phone_app") or ""
            if friend or app:
                excerpt = f"Distractions include {friend} and app {app}."

        last_question = (meta.get("last_question") or "").strip()
        context = {
            "user_text": session.raw_initial_text or "",
            "filled_slots": session.filled_slots,
            "domain": domain,
            "slot": slot,
            "causes": meta.get("causes") or {},
        }
        context["meta"] = {"last_question": last_question}

        if slot == "__generic__":
            generic = get_generic_domain_question(domain)
            if generic:
                next_slot, generic_question = generic
                if generic_question == last_question:
                    add_negated_slots(session.filled_slots, [next_slot])
                    attempts += 1
                    continue
                slot, question = next_slot, generic_question
                break
            attempts += 1
            continue

        question = generate_question(domain, slot, excerpt=excerpt, context=context)
        if question:
            break

        generic = get_generic_domain_question(domain)
        if generic:
            next_slot, generic_question = generic
            if generic_question == last_question:
                add_negated_slots(session.filled_slots, [next_slot])
                attempts += 1
                continue
            slot, question = next_slot, generic_question
            break

        add_negated_slots(session.filled_slots, [slot])
        attempts += 1

    if not question:
        return _complete_session(session)

    session.history.append({"role": "assistant", "text": question})
    meta["total_questions_asked"] = total_questions + 1
    domain_counts[domain] = int(domain_counts.get(domain, 0)) + 1
    meta["domain_question_count"] = domain_counts
    meta["current_question"] = {"domain": domain, "slot": slot, "question": question}
    meta["last_question"] = question
    session.meta = meta

    save_session(session)

    return jsonify(
        {
            "done": False,
            "domain": domain,
            "slot": slot,
            "question": question,
            "meta": session.meta,
        }
    )


@bp.get("/<session_id>/status")
def status(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404
    return jsonify(
        {
            "session_id": str(session.id),
            "status": session.status,
            "active_domains": session.active_domains,
            "filled_slots": session.filled_slots,
            "meta": session.meta,
        }
    )


@bp.get("/<session_id>/debug")
def debug_session(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404
    return jsonify(
        {
            "id": str(session.id),
            "status": session.status,
            "popups_count": len(session.popups or []),
            "popups": session.popups or [],
            "filled_slots": session.filled_slots,
            "meta": session.meta,
        }
    )


@bp.post("/<session_id>/start-simulation")
def start_simulation(session_id: str):
    session = get_session(session_id)
    if not session or session.status != "completed":
        return jsonify({"error": "session not completed"}), 400

    start_popup_simulation(session_id, session.popups or [])
    return jsonify({"ok": True, "popups_scheduled": len(session.popups or [])})


@bp.post("/<session_id>/test-popup")
def test_popup(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404

    payload = {
        "type": "distraction",
        "message": "Test popup ✅\nIf you see this, WS works.",
        "ttl": 8000,
    }
    socketio.emit("popup", payload, room=str(session_id))
    return jsonify({"ok": True, "sent": True, "payload": payload})


def _complete_session(session):
    session.status = "completed"
    stress_profile = session.filled_slots or {}
    inferred_signals = infer_emotion_signals(stress_profile)
    stored_signals = (session.meta or {}).get("emotion_signals") or []
    emotion_signals = list(dict.fromkeys(stored_signals + inferred_signals))
    popups = generate_popups(stress_profile, emotion_signals)
    session.popups = popups
    save_session(session)
    return jsonify(
        {
            "done": True,
            "status": session.status,
            "popups_ready": True,
            "popups_count": len(session.popups or []),
            "filled_slots": session.filled_slots,
        }
    )
