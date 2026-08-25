# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A local-only Project Management MVP: Next.js Kanban frontend + Python FastAPI backend, packaged into a single Docker container (FastAPI serves the built Next.js static export at `/`). Users sign in, manage one or more Kanban boards, and can chat with an AI (via OpenRouter) that edits the board through structured `boardUpdate` actions.

Full business requirements and phased implementation history live in `AGENTS.md` (root) and `docs/PLAN.md`. Each of `backend/`, `frontend/`, and `scripts/` has its own `AGENTS.md` describing that area's current state and responsibilities — read the relevant one before working in that folder, and keep it up to date after making changes there (per `docs/PLAN.md`'s "Working documentation" policy).

## Commands

### Frontend (`frontend/`)

```bash
npm install
npm run dev            # dev server on :3000
npm run build           # next build -> static export in frontend/out
npm run lint
npm run test:unit       # vitest run
npm run test:unit:watch # vitest watch mode
npm run test:e2e        # playwright (auto-starts dev server on :3000)
npm run test:all        # unit then e2e
```

Run a single vitest file/test: `npx vitest run src/components/KanbanBoard.test.tsx -t "test name"`.
Run a single playwright test: `npx playwright test tests/kanban.spec.ts -g "test name"`.

### Backend (`backend/`)

No `uv`/venv is currently set up in this checkout; install deps with pip and run pytest/uvicorn directly:

```bash
pip install -r requirements.txt
pytest                              # run all backend tests (from backend/)
pytest test/test_api.py -k name     # run a single test
uvicorn app.main:app --reload --app-dir backend  # run backend alone (no static frontend build)
```

Note: `AGENTS.md` states the intent to use `uv` as the Python package manager; the current `Dockerfile` and this checkout use plain `pip`.

### Full app (Docker)

```bash
scripts/start.ps1   # Windows: docker build + run, mounts .env, serves on :8000
scripts/stop.ps1
scripts/start.sh    # macOS/Linux equivalent
scripts/stop.sh
```

`OPENROUTER_API_KEY` must be set in a root-level `.env` file — it's passed into the container with `--env-file .env` and used for AI chat calls.

## Architecture

**Build/serve pipeline**: the root `Dockerfile` builds the Next.js app (`next build`, static export to `frontend/out`) in one stage, then copies that output into `backend/app/static` in a `python:3.12-slim` stage. FastAPI serves `index.html` for `/` and any non-`/api/*`, non-static path (SPA-style fallback in `backend/app/main.py`'s catch-all route), so client-side routing works after a full page load.

**Auth**: cookie-based sessions, but sessions live in an in-process `dict` (`sessions` in `backend/app/main.py`), not the database — they reset on backend restart. Passwords are hashed with PBKDF2-HMAC-SHA256 (600k iterations, per-password salt) before being stored in SQLite (`backend/app/db.py`); a hardcoded default `user`/`password` account is seeded on first run.

**Data model / persistence** (`backend/app/db.py`): SQLite at `backend/app/database.db`, created and migrated automatically in `init_db()` (called from the FastAPI lifespan). Two tables: `users` (username/password) and `boards` (`user_id`, `title`, `data` — the entire board as a JSON blob). Every board read/write is scoped by `user_id` in the SQL `WHERE` clause — this is the ownership boundary, not an app-layer check. A new user gets a default board seeded from `backend/app/board.json` if present, else a hardcoded `DEFAULT_BOARD`.

**Board shape**: `{ columns: [{id, title, cardIds: [...]}], cards: {[id]: {id, title, details}} }` — columns hold ordered card-id lists rather than embedding cards, so moving a card is a cardIds edit, not a card mutation. This shape is duplicated as Pydantic models in `backend/app/schemas.py` and TypeScript types in `frontend/src/lib/kanban.ts`; keep both in sync when changing the board schema.

**AI integration** (`backend/app/ai.py`): calls OpenRouter's chat completions endpoint directly via `urllib` (no SDK dependency), model hardcoded to `openai/gpt-oss-120b`. The prompt instructs the model to return JSON with a `message` string and optional `boardUpdate`; `_parse_response_text` extracts the first `{...}` block from the raw completion text (defensively, since models don't always return clean JSON). `boardUpdate` can be either a full `BoardData` replacement or a partial action-style dict — `frontend/src/lib/kanban.ts`'s `applyBoardUpdate()` (used by `AIChatPanel.tsx`) is what actually reconciles that into board state client-side.

**Frontend structure**: `src/app/page.tsx` is the entry point, switching between `LoginForm` and `KanbanBoard` based on restored auth state. `KanbanBoard.tsx` owns board state, drag-and-drop (via `@dnd-kit`), and API calls to `/api/boards*`; `AIChatPanel.tsx` is a sidebar that posts to `/api/ai/chat` and applies the returned `boardUpdate`. Board persistence is explicit round-trips to the backend (`GET`/`PUT /api/boards/{id}`), not optimistic local-only state.

## Coding standards (from `AGENTS.md`)

- Keep it simple — no over-engineering, no speculative abstraction, no unnecessary defensive programming.
- When debugging, find the root cause before attempting a fix; don't guess.
- No emojis, ever.
- Use idiomatic, current-as-of-today library usage.
