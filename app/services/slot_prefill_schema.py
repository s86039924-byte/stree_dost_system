"""Schema for slot prefilling via LLM."""
from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

DomainId = Literal[
    "distractions",
    "academic_confidence",
    "time_pressure",
    "social_comparison",
    "family_pressure",
    "motivation",
    "demotivation",
    "backlog_stress",
]

PrefillMap = Dict[str, Dict[str, str]]


class SlotPrefillResponse(BaseModel):
    active_domains: List[DomainId] = Field(default_factory=list)
    prefill: PrefillMap = Field(default_factory=dict)
    negated_slots: List[str] = Field(default_factory=list)


__all__ = ["SlotPrefillResponse", "DomainId", "PrefillMap"]
