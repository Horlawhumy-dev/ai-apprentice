# Demo script

A reliable end-to-end run of **Capture → Map → Teach**.

## 0. Start the stack

```bash
# Backend (PostgreSQL must be running; create the DB once)
createdb ai_apprentice
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## 1. Capture

1. Open `/demo-erp` in one browser tab and `/expert` in another.
2. On `/expert`, click **Create session**, then **Start screen share** and pick the `/demo-erp` tab.
3. Work the invoice:
   - **View supplier history** → emits `supplier_history_viewed`.
   - Change **Cost center** to **CAPEX** → emits `field_changed`.
   - Type a rationale in the interviewer panel → stored as a transcript segment.
   - Leave **Asset number** empty.
4. Demonstrate privacy: click **Pause capture** (events stop), then **Off Record** (events are
   rejected with HTTP 400; the interval becomes a gap), then **Resume capture**.
5. Click **Finish task**.

## 2. Map

6. Answer the three debrief follow-ups and click **Generate Work Map**.
7. Open the Work Map. Show:
   - the time-ordered timeline with actions, decisions, and reasons;
   - the `require_asset_number` guardrail step and its evidence;
   - AI-proposed vs. expert-confirmed review status.
8. Edit a reason, mark a step uncertain, then **Confirm** the guardrail step and **Confirm workflow**.

## 3. Teach

9. From the footer click **Train with this map** (or open `/apprentice?workflow=<id>`).
10. Load the different case **Invoice INV-5120 / Acme Tooling / $8,400**.
11. Press **Save** with no asset number → the tutor **blocks** the save, explains the confirmed
    guardrail, and links back to the expert evidence moment.
12. Enter asset number **A-1001** and **Save** → allowed.
13. Click **Finish case** to see the summary (attempts / blocked / allowed).

## Automated equivalent

`backend/tests/test_e2e.py` runs this exact loop (capture → map → confirm → teach → block →
correct) plus off-record rejection and finish idempotency.
