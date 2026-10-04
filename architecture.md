# Architecture

AI Apprentice implements the full loop: **Capture → Map → Teach**.

## Scope

This repository currently contains **the FastAPI backend only**. The Next.js frontend that the
diagram below describes is not present. Sections covering browser routes, the capture SDK, and
`NEXT_PUBLIC_API_URL` document the intended full-stack design and the contract the backend
implements — they are not runnable from this repo as it stands.

Everything under *Session state machine*, *Provider integration*, and *Guardrails* describes code
that is present and covered by tests. `tests/test_e2e.py` exercises the whole Capture → Map →
Teach loop against the API directly, without a browser.

```
Browser (Next.js App Router) — NOT PRESENT IN THIS REPO
├── /                 landing
├── /expert           Expert Capture (screen share, pause, off-record, finish, debrief)
├── /work-map/[id]    Review timeline, edit/confirm/reject steps, confirm workflow
└── /apprentice       Trainee case, deterministic guardrail evaluation, evidence link
              │ HTTPS JSON
              ▼
FastAPI backend
├── /api/sessions        session lifecycle + events + transcript + questions + work-map
├── /api/workflows       workflow + step review/confirmation
├── /api/apprentice      case templates + evaluation + attempt history
└── /api/voice           provider config (ElevenLabs if configured, else unavailable)
              │
              ▼
PostgreSQL (SQLAlchemy)
```

## Data flow

1. **Capture** — The expert creates a session on `/expert` and shares the workspace with
   `getDisplayMedia`. Structured events come from a real application instrumented with
   `public/sdk/ai-apprentice-capture.js`, which posts events
   (`field_changed`, `click`, `decision`, `save_attempted`, …) to
   `/api/sessions/{id}/events`. `/expert` polls the session so events from a real app appear live.
2. **Map** — After `finish`, the expert answers debrief questions. `/work-map/generate` time-orders
   events, transcript segments, and expert answers into `WorkflowStep` rows with evidence links,
   confidence, and proposed guardrails. The expert confirms/edits/rejects each step and confirms the
   workflow. Unconfirmed rules are clearly marked and never used to block trainee work.
3. **Teach** — The trainee opens `/apprentice`, supplies the confirmed `workflow_id` plus a case the
   expert never saw (a `case_id` and a JSON body). The page derives its inputs from the work map's own
   guardrails, and each submitted action is evaluated by `GuardrailService`. Blocking rules prevent the
   action, explain the rule, and link back to the expert's own evidence step.

## Instrumenting a real system

`public/sdk/ai-apprentice-capture.js` is a dependency-free script any web app can include. It posts
events with the session id supplied by the capture UI and gates emission on the server-side session
status polled every few seconds, so Pause and Off Record stop telemetry from the real app too.

> The SDK itself lived at `frontend/public/sdk/ai-apprentice-capture.js` and is **not present in this
> repo**. The server-side contract it targets (`/api/sessions/{id}/events`, session-status gating) is
> present and exercised by the tests.

```html
<script src="http://localhost:3000/sdk/ai-apprentice-capture.js"
        data-api-url="http://localhost:8000"
        data-session-id="<SESSION_ID>"
        data-source="my_real_app"
        data-auto-track="true"></script>
```

Event contract (all optional keys except `type`): `{ client_event_id, timestamp_ms, source, type, data }`.
Recognised `type`s map to Work Map actions; anything else is kept as a generic step.
`data.action`, `data.decision`, `data.reason`, and `data.guardrails[]` let an app attach intent and
rules directly. Auto-track maps clicks to `click`, input changes to `field_changed`
(`data.field`, `old_value`, `new_value`), and form submits to `save_attempted`. Password fields and
elements marked `data-ai-apprentice-ignore` are never captured.

Rules are extracted from what the expert actually did: every `decision` and `save_attempted` event
contributes its `reason` and any attached `guardrails[]` to the step it produced. Nothing is inferred
from a built-in template.

## Session state machine

```
created -> capturing -> paused -> capturing
                  |          |
                  v          v
              off_record -> capturing (explicit resume)
                  |
                  v
               finishing -> finished
```

Transitions are enforced server-side in `SessionService`. Events and transcript writes are rejected
for `off_record` and `finished` sessions. Off-record intervals are represented as gaps, never as
captured content. `finish` is idempotent.

## Privacy

- Screen/audio capture begins only from an explicit user click and shows persistent status.
- **Off Record** stops capture and causes the backend to reject subsequent events/transcript.
- Provider secrets live only in backend environment variables; only `NEXT_PUBLIC_API_URL` is public.
- Nothing is seeded or synthetic. Every work map comes from a real capture session.

## Provider integration

- **Voice**: `/api/voice/config` reports whether ElevenLabs is configured. When it is, the browser
  calls `POST /api/voice/token`, and the backend exchanges its API key for a short-lived signed
  WebSocket URL (valid ~15 minutes) via ElevenLabs' `get-signed-url`. The API key and the raw
  agent id never leave the server. When ElevenLabs is not configured, the endpoint returns `503`
  and the UI shows that it is unavailable rather than substituting fake audio. Transcript segments
  carry a constrained `source` of `voice_provider`, so provenance stays queryable.
- **Interviewer (LLM)**: `QuestionPolicyService` is model-driven when `LLM_API_KEY` is set. It sends
  recent events + transcript + session state + remaining budget to the Anthropic Messages API and
  expects a validated `{should_ask, question_type, question, trigger_event_id, rationale_for_internal_logging}`
  (live) or `{"questions": [...]}` (debrief). Invalid JSON, bad types, or unknown trigger ids are
  rejected; anything missing is topped up by the deterministic policy. With no key (and in tests) the
  deterministic policy runs alone, so behavior is predictable offline. Model/base URL come from
  `LLM_MODEL` / `LLM_BASE_URL`.
- **Vision**: `VisionService` is an optional corroboration layer and is not required for the loop.
  Structured events from instrumented applications are the source of truth.

## Guardrails

Guardrails are not built in. Each rule is a `guardrails[]` entry the expert attached to a captured
step, evaluated by `GuardrailService`. Evaluation is domain-neutral and happens in two modes:

| mode | when | behaviour |
| --- | --- | --- |
| structured | rule carries a `condition` object (e.g. `requires_fields`) | evaluated deterministically in Python |
| natural language | rule is prose only | judged by the LLM; returns `unreviewed` when the LLM is unavailable |

A rule id is generated per step, so `matched_rule_id` always links back to the exact step that
defined it — that link is what `evidence` returns to the apprentice.

The threshold and policy are demo data only.
