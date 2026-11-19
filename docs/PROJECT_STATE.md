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
| #29 User authentication | complete (PR #64 merged) |
| #30 Frontend app shell | complete (PR #66 merged) |
| #31 Profile model and API | complete (PR #65 merged) |
| #32 Job preferences | complete (PR #67 merged) |
| #35 Employer registry | complete (PR #68 merged) |
| #36 ATS detection | complete (PR #69 merged) |
| #37 Feed clients (Greenhouse/Lever) | complete (PR #70 merged) |
| #39 Discovery service | complete (PR #71 merged) |
| #42 Content retrieval | complete (PR #72 merged) |
| #43 AI gateway | complete (PR #73 merged) |
| #44 Job analysis pipeline | complete (PR #74 merged) |

## Repo layout

- `backend/` — FastAPI app: `app/main.py` (app factory), `app/config.py` (pydantic-settings incl. AUTH_JWT_SECRET), `app/security.py` (bcrypt+PyJWT), `app/api/auth.py` (register/login/me, get_current_user dependency), `app/db.py` (Base, UuidPkMixin, TimestampMixin, session_scope), `app/models/user.py`, Alembic in `migrations/`; pytest in `tests/` with fresh-per-session test DB via migrations + per-test rollback; uv-managed
- Local dev DB port is 5438 (host 5432 is taken by other projects); dev db container must be started (`docker compose up -d db`) before alembic/pytest
- Backend architecture: app/api/* routers (auth, profile, preferences, employers, discovery, analysis), app/services/* (discovery, analysis), app/providers/* (detection, greenhouse/lever clients, jobs DTO with throttling+backoff), app/ai/gateway.py (Claude gateway), app/scraping.py (safe fetch, robots, SSRF guard, retrieval w/ TTL cache)
- AI gateway contract: complete(task_type, prompt, model_tier, max_tokens, critical, user_id, session) -> GatewayResult(status completed|cache_hit|skipped_budget); tests inject a fake caller via gateway.set_caller; ai_cache/ai_usage_logs tables must be cleaned between tests via session_scope (db_session fixture rolls back)
- `frontend/` — Vite React TS (`src/App.tsx` pings `/healthz`), `package-lock.json` committed
- `docker-compose.yaml` — db (pgvector/pg16), api, worker (placeholder), frontend
- `.github/workflows/ci.yml` — backend ruff+mypy+pytest, frontend build; runs on PRs and pushes to main

## Commands

```bash
cd backend && uv sync --dev && uv run ruff check . && uv run mypy app && DATABASE_URL=postgresql+psycopg://career_radar:career_radar@localhost:5438/career_radar uv run pytest -q
cd frontend && npm ci && npm run build
docker compose up   # local stack
```

## Conventions

- Never push directly to `main`; feature PRs only, squash merge.
- No secrets committed; `.env` ignored; AI tests must use mocks/fixtures only.
- Ruff line length 100; mypy `disallow_untyped_defs`; tests ignore S101.

## Next actions

1. Merge PR for #27, close it.
2. Next eligible: #45 sponsorship classification (deps: #44 done), then #40 historical discovery, #41 availability recheck, #46 Nigeria eligibility.
3. Then Epic 7 matching (#47) which needs analysis + sponsorship outputs.
4. Then job management (#49), documents (#51/#52), applications (Epic 10).
