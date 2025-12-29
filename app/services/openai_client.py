"""Shared OpenAI chat helpers."""
from __future__ import annotations

from openai import OpenAI

client = OpenAI()


def chat_text(model: str, system: str, user: str, **kwargs):
    """Basic chat completion returning text."""
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )


def chat_json(model: str, system: str, user: str):
    """Chat completion forced to return JSON object."""
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )


__all__ = ["chat_text", "chat_json"]
