"""Background popup scheduler."""
from __future__ import annotations

import threading
import time

from ..extensions import socketio


def start_popup_simulation(session_id: str, popups: list[dict]) -> None:
    """Emit popup payloads sequentially into session-specific room."""

    def run() -> None:
        room = str(session_id)
        for popup in list(popups or []):
            socketio.emit("popup", popup, room=room)
            time.sleep(3)
            socketio.emit("popup", popup, room=room)

    threading.Thread(target=run, daemon=True).start()


__all__ = ["start_popup_simulation"]
