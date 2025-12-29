"""Pydantic schemas for popup generation."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

PopupType = Literal["distraction", "self_doubt", "panic", "pressure", "motivation"]

TYPE_MAP = {
    "stress": "panic",
    "anxiety": "panic",
    "fear": "panic",
    "panic": "panic",
    "parental_pressure": "pressure",
    "doubt": "self_doubt",
    "selfdoubt": "self_doubt",
    "self_doubt": "self_doubt",
    "pressure": "pressure",
    "motivation": "motivation",
    "distraction": "distraction",
    "girlfriend": "distraction",
}


class Popup(BaseModel):
    type: PopupType
    message: str = Field(..., min_length=5, max_length=180)
    ttl: int = Field(..., ge=3000, le=15000)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value):
        if not isinstance(value, str):
            return value
        key = value.strip().lower().replace("-", "_").replace(" ", "_")
        return TYPE_MAP.get(key, key)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return "\n".join(
            " ".join(line.strip().split())
            for line in value.strip().split("\n")
            if line.strip()
        )


class PopupResponse(BaseModel):
    popups: List[Popup]


__all__ = ["PopupType", "Popup", "PopupResponse"]
