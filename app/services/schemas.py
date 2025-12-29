"""Pydantic schemas for GPT extraction."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

ComponentId = Literal[
    "academic_confidence",
    "time_pressure",
    "distractions",
    "social_comparison",
    "family_pressure",
    "motivation",
    "demotivation",
    "backlog_stress",
]


class ExtractedComponent(BaseModel):
    id: ComponentId
    excerpt: str = Field(..., min_length=1, max_length=160)

    @field_validator("excerpt")
    @classmethod
    def normalize_excerpt(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ExtractComponentsResponse(BaseModel):
    components: List[ExtractedComponent] = Field(default_factory=list)


__all__ = ["ComponentId", "ExtractedComponent", "ExtractComponentsResponse"]
