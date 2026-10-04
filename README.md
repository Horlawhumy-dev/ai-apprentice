# AI Apprentice

AI system that captures expert workflows, maps decisions and guardrails, and teaches new
employees through unseen cases. Implements the full **Capture → Map → Teach** loop.

## Stack

- **frontend**: Next.js (App Router), React, TypeScript, Tailwind CSS
- **backend**: FastAPI, Pydantic, SQLAlchemy, PostgreSQL
- **voice**: ElevenLabs when configured, otherwise a clearly-labelled prototype transcript mode

## Run locally

### Backend

```bash
createdb ai_apprentice          # once
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # adjust DATABASE_URL if needed
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

Set `DATABASE_URL` to a PostgreSQL URL, e.g.
`postgresql+psycopg2://postgres:postgres@localhost:5432/ai_apprentice` or the unix-socket form
`postgresql+psycopg2:///ai_apprentice`.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Landing with links to the three modes |
| `/expert` | Expert Capture: screen share, pause/off-record/finish, debrief, SDK snippet |
| `/demo-erp` | Fictional invoice ERP that emits structured events |
| `/work-map/[workflowId]` | Review timeline, edit/confirm/reject steps |
| `/apprentice` | Trainee case, guardrail evaluation, evidence link |

## Capture your own system (instrumentation SDK)

The demo ERP only exists to emit structured events deterministically. To capture a real
application, add the SDK — it streams clicks, field changes and submits to the active
capture session, and stops on Pause/Off Record.

```html
<script src="http://localhost:3000/sdk/ai-apprentice-capture.js"
        data-api-url="http://localhost:8000"
        data-session-id="<SESSION_ID_FROM_THE_CAPTURE_UI>"
        data-source="my_real_app"
        data-auto-track="true"></script>
```

Or programmatically: `AIApprentice.init({ apiUrl, sessionId, autoTrack: true })`.
Log reasoning with `AIApprentice.decision("why...", { decision, guardrails })`. Mark
specific controls with `data-ai-apprentice="event_type"`, exclude sensitive fields with
`data-ai-apprentice-ignore`. The SDK never sends while the session is paused or off
record. See `docs/architecture.md` for the event contract.

## Tests

```bash
cd backend
pytest -v
```

`tests/test_e2e.py` covers the complete loop, off-record rejection, and finish idempotency.

See `docs/architecture.md` and `docs/demo-script.md` for design and a scripted walkthrough.
