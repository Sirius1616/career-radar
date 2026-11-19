# Project state (continuation notes)

Keep this document current so a fresh coding session can resume without rescanning the repo.

## Product

Career Radar — AI-driven job discovery/intelligence/matching/application platform.
Full requirements and approved stack: see the original product brief (this repo's issues).
Key principles: modular monolith, cheap to run, Claude API only with strict cost controls,
PostgreSQL-backed durability, no Redis/K8s/aggregator APIs.

## GitHub backlog

- Repo: https://github.com/Sirius1616/career-radar (default branch `main`, feature-branch workflow)
- Epics: #1–13 (labels: `epic`). Implementation issues: #27–62.
- Milestones: M1 Foundation (#4), M2 Discovery and intelligence (#1), M3 Matching and applications (#2), M4 Automation and operations (#3).
- Labels: epic, feature, backend, frontend, infrastructure, database, ai, security, testing, bug, documentation, priority:*, blocked.

Key dependency chain:
#27 scaffold → #28 DB foundation → #29 auth → (#31 profile, #32 preferences) →
(#35/#36 employer+ATS detection, #37/#38 feeds) → #39 discovery → (#42 retrieval, #43 AI gateway)
→ #44 analysis → (#45 sponsorship) → #47 matching → (#49 saved jobs, #51/#52 documents) →
(#53 applications, #54 forms, #55 submission) → (#56 queue, #57 scheduler) → (#59/#60 activity) →
(#61 security, #62 deployment).

## Progress

| Issue | Status |
|---|---|
| #27 Foundation scaffold, Compose, CI | complete (closed) |
| #28 Database foundation | complete (PR #63 merged) |
| #29 User authentication | implemented, PR open |

## Repo layout

- `backend/` — FastAPI app: `app/main.py` (app factory), `app/config.py` (pydantic-settings incl. AUTH_JWT_SECRET), `app/security.py` (bcrypt+PyJWT), `app/api/auth.py` (register/login/me, get_current_user dependency), `app/db.py` (Base, UuidPkMixin, TimestampMixin, session_scope), `app/models/user.py`, Alembic in `migrations/`; pytest in `tests/` with fresh-per-session test DB via migrations + per-test rollback; uv-managed
- Local dev DB port is 5438 (host 5432 is taken by other projects)
- `frontend/` — Vite React TS (`src/App.tsx` pings `/healthz`), `package-lock.json` committed
- `docker-compose.yaml` — db (pgvector/pg16), api, worker (placeholder), frontend
- `.github/workflows/ci.yml` — backend ruff+mypy+pytest, frontend build; runs on PRs and pushes to main

## Commands

```bash
cd backend && uv sync --dev && uv run ruff check . && uv run mypy app && uv run pytest -q
cd frontend && npm ci && npm run build
docker compose up   # local stack
```

## Conventions

- Never push directly to `main`; feature PRs only, squash merge.
- No secrets committed; `.env` ignored; AI tests must use mocks/fixtures only.
- Ruff line length 100; mypy `disallow_untyped_defs`; tests ignore S101.

## Next actions

1. Merge PR for #27, close it.
2. Merge #29 PR.
3. Next: #31 profile model+API, then #32 preferences, then Epic 3 (#35 employer registry, #36 ATS detection).
