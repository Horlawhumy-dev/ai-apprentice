# AI Apprentice

AI system for capturing expert workflows, mapping decisions and
guardrails, and teaching new employees through unseen cases.

## Applications
- frontend: Next.js, React, TypeScript, Tailwind CSS
- backend: FastAPI, Pydantic, Python

## Run locally

Frontend:
  cd frontend
  cp .env.example .env.local
  npm run dev

Backend:
  cd backend
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  uvicorn app.main:app --reload

API docs: http://localhost:8000/docs
