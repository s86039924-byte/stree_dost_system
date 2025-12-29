"""Database models."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from sqlalchemy import JSON, func
from sqlalchemy.ext.mutable import MutableDict, MutableList

from ..extensions import db

USE_SQLITE = (os.getenv("DATABASE_URL") or "").startswith("sqlite")

if USE_SQLITE:
    UUIDType = db.String(36)
    JSONType = JSON

    def _uuid_default() -> str:
        return str(uuid.uuid4())

else:
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    UUIDType = UUID(as_uuid=True)
    JSONType = JSONB

    def _uuid_default() -> uuid.UUID:
        return uuid.uuid4()


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(UUIDType, primary_key=True, default=_uuid_default)
    status = db.Column(db.String(20), nullable=False, default="active")

    raw_initial_text = db.Column(db.Text, nullable=True)

    history = db.Column(MutableList.as_mutable(JSONType), nullable=False, default=list)
    active_domains = db.Column(MutableList.as_mutable(JSONType), nullable=False, default=list)
    filled_slots = db.Column(MutableDict.as_mutable(JSONType), nullable=False, default=dict)
    meta = db.Column(MutableDict.as_mutable(JSONType), nullable=False, default=dict)
    popups = db.Column(MutableList.as_mutable(JSONType), nullable=False, default=list)

    created_at = db.Column(
        db.DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=datetime.utcnow,
    )


__all__ = ["Session"]
