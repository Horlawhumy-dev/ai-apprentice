# Architecture

AI Apprentice implements the full loop: **Capture → Map → Teach**.

```
Browser (Next.js App Router)
├── /                 landing
├── /expert           Expert Capture (screen share, pause, off-record, finish, debrief)
├── /demo-erp         Fictional invoice ERP that emits structured events
├── /work-map/[id]    Review timeline, edit/confirm/reject steps, confirm workflow
└── /apprentice       Trainee case, deterministic guardrail evaluation, evidence link
              │ HTTPS JSON
              ▼
FastAPI backend
├── /api/sessions        session lifecycle + events + transcript + questions + work-map
├── /api/workflows       workflow + step review/confirmation
├── /api/apprentice      case templates + evaluation + attempt history
└── /api/voice           provider config (ElevenLabs if configured, else prototype transcript)
              │
              ▼
PostgreSQL (SQLAlchemy)
```

## Data flow

1. **Capture** — The expert creates a session on `/expert` and shares the workspace with
   `getDisplayMedia`. The source of structured events is either the built-in `/demo-erp` or a real
   application instrumented with `public/sdk/ai-apprentice-capture.js`. Both post events
   (`field_changed`, `click`, `decision`, `save_attempted`, `invoice_opened`, …) to
   `/api/sessions/{id}/events`. `/expert` polls the session so events from a real app appear live.
2. **Map** — After `finish`, the expert answers debrief questions. `/work-map/generate` time-orders
   events, transcript segments, and expert answers into `WorkflowStep` rows with evidence links,
   confidence, and proposed guardrails. The expert confirms/edits/rejects each step and confirms the
   workflow. Unconfirmed rules are clearly marked and never used to block trainee work.
3. **Teach** — The trainee opens `/apprentice` with the confirmed `workflow_id`, receives a
   *different* deterministic case (`case_alpha`), and each `save_attempted` is evaluated by the
   deterministic guardrail engine. Blocking rules prevent the save, explain the rule, and link back
   to the expert evidence step.

## Instrumenting a real system

`public/sdk/ai-apprentice-capture.js` is a dependency-free script any web app can include. It posts
events with the session id supplied by the capture UI and gates emission on the server-side session
status polled every few seconds, so Pause and Off Record stop telemetry from the real app too.

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

The invoice-specific `require_asset_number` guardrail step is only generated when the session shows
capitalization signals (a `cost_center` change or `asset_number_entered`), so real workflows are not
polluted with demo rules.

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
- Demo data (invoices, suppliers, employees) is synthetic.

## Provider integration

- **Voice**: `/api/voice/config` reports whether ElevenLabs is configured. When it is, the backend
  exposes the agent id and the browser can connect with a short-lived token. When it is not, the UI
  runs in clearly-labelled prototype transcript mode so the rest of the loop is demonstrable.
- **Interviewer (LLM)**: `QuestionPolicyService` is model-driven when `LLM_API_KEY` is set. It sends
  recent events + transcript + session state + remaining budget to the Anthropic Messages API and
  expects a validated `{should_ask, question_type, question, trigger_event_id, rationale_for_internal_logging}`
  (live) or `{"questions": [...]}` (debrief). Invalid JSON, bad types, or unknown trigger ids are
  rejected; anything missing is topped up by the deterministic policy. With no key (and in tests) the
  deterministic policy runs alone, so behavior is predictable offline. Model/base URL come from
  `LLM_MODEL` / `LLM_BASE_URL`.
- **Vision**: `VisionService` is an optional corroboration layer and is not required for the loop.
  Structured demo ERP events are the source of truth.

## Guardrails

The demo guardrails are deterministic and live in `app/services/guardrails.py`:

| rule_id | trigger | severity |
| --- | --- | --- |
| `require_asset_number` | CAPEX at/above the demo threshold with no asset number | block |
| `capex_requires_capitalization` | Above-threshold purchase recorded as OPEX but with an asset number | warn |

The threshold and policy are demo data only.
