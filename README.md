# Stress Dost — Usage Guide

A Flask + Socket.IO app that builds a student stress profile, asks guided questions, then emits stress-test popups and a practice-question panel.

## Setup
- Requirements: Python 3.10+, OpenAI API access (for LLM flows), optional Acadza API access.
- Install:
  ```bash
  cd "/home/saurabh/Desktop/New Folder/stress_dost"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## Configuration (.env)
- `DATABASE_URL=sqlite:///instance/stress.db` (or your Postgres URL)
- `OPENAI_API_KEY=...` (required)
- `SOCKETIO_CORS_ALLOWED_ORIGINS=*` (tighten for prod)
- Flow tuning: `MIN_QUESTIONS` (3), `MAX_QUESTIONS` (6), `MAX_DOMAIN_QUESTIONS` (2)
- Acadza: `ACADZA_API_URL`, `ACADZA_API_KEY`, `ACADZA_AUTH` (optional bearer), `ACADZA_COURSE`, `ACADZA_USER_AGENT`, `ACADZA_VERIFY=true|false`, `QUESTION_IDS_CSV` (path to CSV of IDs)

## Database
- Initialize schema (Flask-Migrate): `flask --app wsgi db upgrade`
- SQLite files: `instance/stress.db`, `instance/stress_dost.db` (point `DATABASE_URL` to the one you want)

## Run / Verify
- Dev server: `python wsgi.py` (http://127.0.0.1:5002)
- Health: `curl http://localhost:5002/health`
- Prod hint: `gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5002 wsgi:app`

## Using the UI (http://localhost:5002/)
- Stage 1: enter an initial vent and click “Launch Session” (`POST /session/start`)
- Stage 2: answer prompts; short answers may trigger a clarifier (`/session/<id>/next-question`, `/answer`)
- Completion: app calls `/session/<id>/start-simulation`, shows popups, then loads practice questions
- HUD shows session ID, domains, trace log, popup console

## API Quickstart (headless)
```bash
# Start session
curl -X POST http://localhost:5002/session/start \
  -H "Content-Type: application/json" \
  -d '{"text":"I keep scrolling reels and exams are close"}'

# Get next question
curl -X POST http://localhost:5002/session/<session_id>/next-question

# Submit answer (include domain/slot if you have them)
curl -X POST http://localhost:5002/session/<session_id>/answer \
  -H "Content-Type: application/json" \
  -d '{"answer":"I study 3 hours","domain":"time_pressure","slot":"study_hours_per_day"}'

# Trigger popup simulation after completion
curl -X POST http://localhost:5002/session/<session_id>/start-simulation

# Debug/status
curl http://localhost:5002/session/<session_id>/status
curl http://localhost:5002/session/<session_id>/debug
```

## Practice Question Service (`app/api/question_routes.py`)
- `GET /api/questions/load-test-questions` → random set from `data/question_ids.csv`
- `GET /api/questions/get-question/<id>` → single question
- `POST /api/questions/prefetch-batch` with `{"question_ids":[...]}` → prefetch
- `POST /api/questions/mutate/<id>` → numeric mutation for SCQ/integer questions
- `GET /api/questions/stats` → count + sample IDs
- Edit `data/question_ids.csv` (header `question_id`) to change the pool

## Realtime / Popups
- Socket.IO default namespace; `server_hello` on connect
- Join room: emit `join_session` with `{session_id:"<id>"}`; popups arrive as `popup`
- Popup generator lives in `app/services/popup_generator.py`; simulation scheduled via `app/realtime/scheduler.py`
- Sanity-check: `POST /session/<id>/test-popup`

## Key Files
- App factory: `app/__init__.py`; config defaults: `app/config.py`
- Domain/slot schema: `app/constants.py`; planner: `app/services/planner.py`; slot prefilling: `app/services/slot_prefill_llm.py`; question generation: `app/services/question_generator.py`
- Frontend: `static/index.html`, `static/app.js`, `static/styles.css`

## Notes
- Network needed for OpenAI/Acadza; without it, only partial fallbacks run.
- Combo questions (see `app/services/combo_specs.py`) may require formatted answers; hints return in responses.
