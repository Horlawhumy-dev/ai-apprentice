# Demo script

A reliable end-to-end run of **Capture → Map → Teach** against the API.

This walks the loop with `curl` because the repository currently contains the FastAPI backend only —
there is no browser UI to click through. Every request below mirrors `tests/test_e2e.py`, which
asserts the same sequence.

## 0. Start the stack

```bash
createdb ai_apprentice            # once
cp .env.example .env              # adjust DATABASE_URL if needed
make venv                         # create venv + install requirements
make run                          # uvicorn app.main:app --reload --port 8000
```

In another shell:

```bash
export API=http://localhost:8000
curl -s $API/api/health | jq      # {"status":"ok",...}
```

API docs: http://localhost:8000/docs

## 1. Capture

Create a session and start recording:

```bash
SID=$(curl -s -X POST $API/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"workflow_title":"Invoice Processing","expert_name":"Demo Expert"}' | jq -r .session_id)

curl -s -X POST $API/api/sessions/$SID/start | jq .status   # "capturing"
```

Post the events an instrumented app would emit — an invoice opened, a cost center flipped to CAPEX,
then a save with no asset number:

```bash
ev() { curl -s -X POST $API/api/sessions/$SID/events \
  -H 'Content-Type: application/json' \
  -d "{\"client_event_id\":\"$(uuidgen)\",\"timestamp_ms\":$1,\"source\":\"demo_erp\",\"type\":\"$2\",\"data\":$3}" \
  -o /dev/null -w '%{http_code}\n'; }

ev 1000 invoice_opened  '{"invoice_id":"INV-4471","amount":7200}'
ev 2000 field_changed   '{"field":"cost_center","old_value":"OPEX","new_value":"CAPEX","invoice_id":"INV-4471"}'
ev 3000 save_attempted  '{"invoice_id":"INV-4471","asset_number":""}'
```

Re-posting an event with the same `client_event_id` is idempotent and still returns `200`.

Record the expert's reasoning, which becomes the evidence link on the guardrail step:

```bash
curl -s -X POST $API/api/sessions/$SID/transcript \
  -H 'Content-Type: application/json' \
  -d "{\"segment_id\":\"$(uuidgen)\",\"timestamp_ms\":2500,\"speaker\":\"expert\",\"source\":\"voice_provider\",\"text\":\"This equipment is above our capitalization threshold, so it needs an asset number.\"}" \
  -o /dev/null -w '%{http_code}\n'
```

## 2. Privacy — Pause and Off Record

Do this **before** finishing: `finished` is terminal (`"finished": set()` in the transition table),
so `off-record` afterwards returns `Invalid transition from finished to off_record`.

**Pause** is a recording control — it flips status to `paused` but the backend still *accepts* events
while paused. **Off Record** is the privacy control — the backend rejects them outright with `400`:

```bash
curl -s -X POST $API/api/sessions/$SID/pause   | jq -r .status   # "paused"
ev 4000 invoice_opened '{"invoice_id":"INV-8888"}'               # 200 — still accepted

curl -s -X POST $API/api/sessions/$SID/off-record | jq -r .status # "off_record"
ev 4100 invoice_opened '{"invoice_id":"INV-9999"}'               # 400 — rejected

curl -s -X POST $API/api/sessions/$SID/resume | jq -r .status    # "capturing"
ev 5000 invoice_opened '{"invoice_id":"INV-4471"}'               # 200 — accepted again
```

The rejected event is refused, not stored, so off-record intervals become **gaps in the timeline,
never content**. Transcript writes are gated the same way.

## 3. Finish and Map

Ask the interviewer whether to interject, then finish (idempotent — repeat it, status stays
`finished`):

```bash
curl -s -X POST $API/api/sessions/$SID/questions/decide | jq .
curl -s -X POST $API/api/sessions/$SID/finish | jq -r .status   # "finished"
curl -s -X POST $API/api/sessions/$SID/finish | jq -r .status   # "finished" again — idempotent
```

Generate the Work Map. Steps arrive as AI-proposed, needing expert review:

```bash
WM=$(curl -s -X POST $API/api/sessions/$SID/work-map/generate)
echo "$WM" | jq .status                       # "needs_expert_review"
echo "$WM" | jq '[.steps[].action]'           # includes change_cost_center, require_asset_number
```

Confirm the guardrail step, then confirm the workflow itself:

```bash
WID=$(echo "$WM" | jq -r .id)
STEP=$(echo "$WM" | jq -r '.steps[] | select(.action=="require_asset_number") | .id')

curl -s -X PATCH $API/api/workflows/$WID/steps/$STEP \
  -H 'Content-Type: application/json' -d '{"review_status":"confirmed"}' | jq .review_status

curl -s -X PATCH $API/api/workflows/$WID \
  -H 'Content-Type: application/json' -d '{"status":"confirmed"}' | jq .status
```

Unconfirmed rules stay clearly marked and are never used to block trainee work.

## 4. Teach

Start the trainee on a **different** case that exercises the same confirmed rule:

```bash
ASID=$(curl -s -X POST $API/api/apprentice/sessions \
  -H 'Content-Type: application/json' \
  -d "{\"workflow_id\":\"$WID\",\"case_id\":\"case_alpha\"}" | jq -r .id)
```

Save with no asset number → **blocked**, with the rule and a link back to the expert evidence:

```bash
curl -s -X POST $API/api/apprentice/sessions/$ASID/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"action":"save_attempted","case_data":{"asset_number":""}}' \
  | jq '{allowed, matched_rule_id, evidence_step_id}'
# allowed=false, matched_rule_id="require_asset_number"
```

Supply an asset number → allowed:

```bash
curl -s -X POST $API/api/apprentice/sessions/$ASID/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"action":"save_attempted","case_data":{"asset_number":"A-1001"}}' \
  | jq .allowed          # true
```

Finish for the attempt tally:

```bash
curl -s -X POST $API/api/apprentice/sessions/$ASID/finish | jq .summary
# {"attempts":2,"blocked":1,"allowed":1}
```

## Automated equivalent

```bash
make test-e2e
```

`tests/test_e2e.py` runs this exact loop (capture → map → confirm → teach → block → correct) plus
off-record rejection and finish idempotency. `make test` runs the full suite.