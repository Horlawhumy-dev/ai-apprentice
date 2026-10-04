# AI Apprentice — Backend

API that captures expert workflows, maps decisions and guardrails, and teaches new employees through
unseen cases. Implements the **Capture → Map → Teach** loop.

> **Scope:** this repository currently contains the **FastAPI backend only**. The Next.js frontend is
> not present. The browser UI and capture SDK documented in `architecture.md` describe the intended
> full-stack design and the server contract this API implements — they are not runnable here.
> Everything else below is present and covered by tests.

## Stack

- **API**: FastAPI, Pydantic v2, Pydantic Settings
- **Persistence**: SQLAlchemy 2, PostgreSQL (`psycopg` v3, with `psycopg2` still supported)
- **Optional providers**: ElevenLabs (voice), Anthropic Messages API (interviewer)
- **Runtime**: Python 3.12

## Setup

Requires Python 3.12+ and a reachable PostgreSQL.

```bash
createdb ai_apprentice            # once
cp .env.example .env              # adjust DATABASE_URL
make venv                         # create venv/ and install requirements
```

`DATABASE_URL` accepts a unix socket (peer auth) or a full TCP URL:

```
postgresql:///ai_apprentice
postgresql://postgres:postgres@localhost:5432/ai_apprentice
```

Driver caveat, which is easy to get wrong: under SQLAlchemy 2.x a bare `postgresql://`
URL resolves to the **psycopg v3** driver, not psycopg2. If `psycopg` is not installed you
get `ModuleNotFoundError: No module named 'psycopg'` at import time, before the app can
serve a request. Both drivers are installed, so `postgresql://`, `postgresql+psycopg://`
and `postgresql+psycopg2://` all work. Hosted providers (Neon, Supabase) hand you a bare
`postgresql://` URL, so use that form and you avoid the question entirely.

## Run

```bash
make run                          # uvicorn app.main:app --reload on 0.0.0.0:8000
```

API docs: http://localhost:8000/docs

## Make targets

| Target | Purpose |
| --- | --- |
| `make help` | List all targets |
| `make venv` | Create the virtualenv and install dependencies |
| `make deps` | Refresh dependencies in the existing virtualenv |
| `make run` | Start the API with autoreload (`HOST` / `PORT` overridable) |
| `make test` | Run the full test suite |
| `make test-verbose` | Run the suite verbosely |
| `make test-e2e` | Run only the full Capture → Map → Teach loop test |
| `make db-init` | Create tables in the configured database |
| `make clean` | Remove caches and bytecode |
| `make distclean` | Also remove the virtualenv |

Targets invoke tools as `venv/bin/python -m ...` rather than `venv/bin/<tool>`, because console
scripts hardcode an absolute interpreter path and break if the virtualenv is moved. If `pytest`,
`pip`, or `uvicorn` stop working from `venv/bin`, run `make distclean && make venv`.

## Configuration

All settings are read from the environment (or `.env`) via `app/core/config.py`.

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2:///ai_apprentice` | Required in practice |
| `ENVIRONMENT` | `development` | `production` disables the permissive CORS regex |
| `APP_NAME` | `AI Apprentice API` | |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-list; meaningful once a UI exists |
| `EXTRA_ALLOWED_ORIGINS` | *(empty)* | Comma-separated additional CORS origins |
| `LLM_API_KEY` | *(empty)* | Blank ⇒ deterministic question policy, fully offline |
| `LLM_BASE_URL` | `https://api.anthropic.com` | |
| `LLM_MODEL` | `claude-3-5-sonnet-latest` | |
| `ELEVENLABS_API_KEY` | *(empty)* | Blank ⇒ prototype transcript mode |
| `ELEVENLABS_AGENT_ID` | *(empty)* | |

Tables are created on startup via `init_db()`; `make db-init` does the same on demand.

## API

All routes are prefixed `/api`. Machine-readable schema at `/openapi.json`.

| Area | Routes |
| --- | --- |
| Health | `GET /api/health`, `GET /api/tutor/health`, `GET /api/voice/config` |
| Session lifecycle | `POST /api/sessions`, `GET /api/sessions/{id}`, `POST .../start`, `.../capture/start`, `.../pause`, `.../resume`, `.../off-record`, `.../finish` |
| Capture | `POST .../events`, `POST .../transcript` |
| Interview | `POST .../questions/decide`, `POST .../debrief`, `POST .../questions/{question_id}/answer` |
| Map | `POST .../work-map/generate`, `GET /api/workflows/{id}`, `PATCH /api/workflows/{id}`, `PATCH /api/workflows/{id}/steps/{step_id}` |
| Teach | `GET /api/apprentice/cases`, `GET /api/apprentice/cases/{case_id}`, `POST /api/apprentice/sessions`, `GET .../sessions/{id}`, `POST .../evaluate`, `POST .../finish` |
| Voice | `POST /api/voice/token` |

Transcript segments accept a constrained `source` of `voice_provider` or `prototype_transcript`;
anything else is rejected with `422`. Event `source` stays free-form on purpose, since
third-party apps instrumented via the capture SDK set their own.

### Session state machine

```
created -> capturing -> paused -> capturing
                  |          |
                  v          v
              off_record -> capturing (explicit resume)
                  |
                  v
               finishing -> finished
```

Transitions are enforced server-side. `finished` is terminal. Event and transcript writes are
rejected with `400` only for `off_record` and `finished` sessions — **`paused` still accepts them**,
since pause is a recording control rather than a privacy control. Off-record intervals become gaps
in the timeline, never content. `finish` is idempotent.

## Tests

```bash
make test                         # 7 tests
make test-e2e                     # the full loop, off-record, idempotency
```

`tests/test_e2e.py` covers the complete loop plus off-record rejection and finish idempotency.
Tests force the deterministic question policy, so they need no API keys and no network.

## Demo

```bash
make run                         # in one shell
```

Then follow [`demo-script.md`](demo-script.md), which walks the whole loop with `curl` + `jq`. Every
command in it has been executed against a live server. Requires `jq`.

## Further reading

- [`architecture.md`](architecture.md) — data flow, event contract, guardrails, provider integration
- [`demo-script.md`](demo-script.md) — API-driven end-to-end walkthrough

## Deploying to Vercel

`vercel.json` configures the Python runtime. Import the repo and leave **Root Directory at the
repository root** — the backend *is* the root, and `app/main.py` is a documented entrypoint location
that exposes a top-level `app`, so the FastAPI framework preset is detected automatically and routes
every request to the app unchanged.

`vercel.json` sets:

- `maxDuration: 60` — interviewer and voice calls are slow; this is the Hobby ceiling
- `excludeFiles` — Python bundles are not tree-shaken, so `venv/`, `tests/`, and `.env*` are excluded
  to keep the bundle small and to keep local secrets out of it
- `regions` — set this to match your database

Deliberately **not** set: `rewrites` and `routes`. Adding them would double-prefix the API paths
into `/api/api/...`, and `functions` cannot be combined with the legacy `builds` key.

Do **not** add a `pyproject.toml` unless you also migrate dependencies into it. Vercel prefers
`pyproject.toml` over `requirements.txt` when both exist without a lockfile, and will install
nothing — producing a runtime `ModuleNotFoundError` for FastAPI.

Required environment variables in the Vercel project: `DATABASE_URL`, `ENVIRONMENT=production`,
`FRONTEND_ORIGIN`, plus `LLM_API_KEY` / `ELEVENLABS_API_KEY` if those providers are wanted. Note that
Vercel has no local PostgreSQL: point `DATABASE_URL` at a hosted database (Neon, Supabase, …).