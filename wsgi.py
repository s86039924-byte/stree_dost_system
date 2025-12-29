"""Gunicorn entrypoint."""
from __future__ import annotations

import os

from app import create_app
from app.extensions import socketio

app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    socketio.run(app, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True)
