# Career Radar

AI-driven job discovery, intelligence, matching and application automation platform.

Discovers vacancies from genuine employers' official career pages and supported ATS public
feeds, analyses them (requirements, visa sponsorship, match scoring), prepares tailored
applications and tracks progress — all running durably in the background.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic (modular monolith + worker process)
- Frontend: React, Vite, TypeScript
- Database: PostgreSQL 16 with pgvector
- AI: Anthropic Claude API (cost-controlled gateway)
- Infra: Docker Compose, single affordable VPS

## Getting started

```bash
cp .env.example .env
docker compose up
```

- API: http://localhost:8000 (health at `/healthz`)
- Frontend: http://localhost:5173

Run backend tests locally:

```bash
cd backend && uv sync --dev && uv run pytest -q
```

## Branch workflow

- `main` is the default branch; never push to it directly.
- Work happens on `feature/*` branches; PRs target `main` and must pass CI.
- Squash-merge PRs; link the GitHub issue in the PR description.
