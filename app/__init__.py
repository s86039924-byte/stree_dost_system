"""Application factory."""
from __future__ import annotations

from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from .api.health_routes import bp as health_bp
from .api.session_routes import bp as session_bp
from .api.ui_routes import bp as ui_bp
from .api.question_routes import init_question_service
from .config import Config
from .extensions import db, migrate, socketio
from .realtime import socket_events  # noqa: F401


def create_app():
    app = Flask(__name__, static_folder="../static", static_url_path="/")
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins=app.config["SOCKETIO_CORS_ALLOWED_ORIGINS"])

    app.register_blueprint(ui_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(health_bp)
    init_question_service(app)

    return app


__all__ = ["create_app"]
