"""Thin repository helpers."""
from __future__ import annotations

from ..extensions import db
from .models import Session


def create_session(raw_initial_text: str) -> Session:
    session = Session(
        raw_initial_text=raw_initial_text,
        history=[{"role": "user", "text": raw_initial_text}],
        active_domains=[],
        filled_slots={},
        meta={
            "total_questions_asked": 0,
            "domain_question_count": {},
            "clarifier_used": [],
            "current_question": None,
            "emotion_signals": [],
            "combo_history": [],
        },
    )
    db.session.add(session)
    db.session.commit()
    db.session.refresh(session)
    return session


def get_session(session_id) -> Session | None:
    return Session.query.get(session_id)


def save_session(session: Session) -> None:
    db.session.add(session)
    db.session.commit()
    db.session.refresh(session)


__all__ = ["create_session", "get_session", "save_session"]
