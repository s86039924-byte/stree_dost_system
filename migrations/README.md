# Alembic Quickstart

From the project root:

1. Export environment (or use `.env`): `export FLASK_APP=wsgi.py`.
2. Initialize (first time only): `flask db init` (already points to `migrations/`).
3. Generate migrations: `flask db migrate -m "describe change"`.
4. Apply migrations: `flask db upgrade`.

`Flask-Migrate` wires Alembic to the app factory, so it will auto-load your models.*** End Patch}>>>
