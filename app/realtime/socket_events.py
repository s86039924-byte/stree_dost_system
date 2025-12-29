"""Socket.IO events."""
from __future__ import annotations

from flask_socketio import emit, join_room

from ..extensions import socketio


@socketio.on("connect")
def on_connect():
    emit("server_hello", {"ok": True, "message": "Socket connected"})


@socketio.on("join_session")
def on_join_session(data):
    session_id = str((data or {}).get("session_id") or "")
    if session_id:
        join_room(session_id)
        emit("joined", {"ok": True, "session_id": session_id})


@socketio.on("disconnect")
def on_disconnect():
    return None
