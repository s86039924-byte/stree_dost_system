"""Environment-driven configuration."""
from __future__ import annotations

import os


class Config:
    ENV = os.getenv("ENV", "dev")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")

    MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", "3"))
    MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "6"))
    MAX_DOMAIN_QUESTIONS = int(os.getenv("MAX_DOMAIN_QUESTIONS", "2"))


__all__ = ["Config"]
