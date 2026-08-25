# The Project Management MVP web app

## Project goal

Build a local MVP that combines a Next.js Kanban frontend, a Python FastAPI backend, SQLite persistence, and an AI chat assistant that can update the board.

## Current implementation status

- Frontend and backend are integrated and deployed in Docker.
- Authentication and board persistence are being upgraded for multiple local users and multiple boards per user.
- AI chat now returns structured `boardUpdate` actions and the frontend applies them to the board.
- `OPENROUTER_API_KEY` is loaded from `.env` and passed into Docker with `--env-file .env`.

## Business requirements

- A user can sign in.
- When signed in, a user can create, select, and update their own Kanban boards.
- The Kanban board has fixed columns that can be renamed.
- Cards can be moved, added, and deleted.
- An AI chat sidebar can create, edit, move, or update cards.

## Limitations

- Local username/password accounts only; there is no external identity provider.
- Local deployment via Docker.

## Technical decisions

- Next.js frontend in `frontend/`.
- Python FastAPI backend in `backend/`.
- Static frontend served from backend at `/`.
- Docker container for local deployment.
- Use `uv` as the Python package manager inside Docker.
- OpenRouter for AI calls with `OPENROUTER_API_KEY` from `.env`.
- Use `openai/gpt-oss-120b` as the model.
- SQLite local database created automatically if missing.
- Start/stop scripts in `scripts/` for Windows/macOS/Linux.

## Project phases

### Part 1: Plan and documentation

Tasks:
- Review the current frontend demo and folder structure.
- Create `frontend/AGENTS.md` describing the frontend state.
- Update `backend/AGENTS.md` and `scripts/AGENTS.md` with their intended responsibilities.
- Confirm the plan before implementation.

Success criteria:
- `docs/PLAN.md` is detailed and actionable.
- Agent docs exist for frontend, backend, and scripts.
- The plan is approved before other work begins.

Verification:
- Manual review of plan and agent files.

### Part 2: Scaffolding

Tasks:
- Add backend FastAPI scaffolding and a minimal API endpoint.
- Add root-level `Dockerfile` and `.dockerignore`.
- Add start/stop scripts in `scripts/`.
- Confirm the backend can serve a sample response locally.

Status:
- Completed. The container builds and runs, and the backend now serves the built frontend.

Success criteria:
- Docker build succeeds.
- Running the container responds to `GET /api/ping`.
- Static file serving is prepared.

Verification:
- Build and run the container.
- Call the API endpoint successfully.

### Part 3: Frontend integration

Tasks:
- Verify `frontend` builds successfully.
- Configure backend to serve the built frontend.
- Ensure the Kanban demo displays at `/`.

Status:
- Completed. The frontend is built inside Docker and served from the backend.

Success criteria:
- `npm run build` passes.
- `/` shows the Kanban UI from the backend.

Verification:
- Build frontend.
- Load the app in a browser.

### Part 4: Fake authentication

Tasks:
- Add a login screen in the frontend.
- Store auth state in the browser.
- Protect the app behind login and add logout.

Status:
- Completed. Sign in/out is implemented in the frontend with local auth state and a `/api/logout` endpoint.

Success criteria:
- `user` / `password` is required before viewing the board.
- Logout returns to the login screen.

Verification:
- Frontend tests for login state.
- End-to-end login/logout test.

### Part 5: Database modeling

Tasks:
- Design a SQLite schema for users and board JSON.
- Document the schema in `docs/`.
- Implement database initialization logic.

Schema:
- `users` table: `id`, `username`, `password`
- `boards` table: `id`, `user_id`, `data`, `created_at`, `updated_at`
- `data` stores the full board JSON for the hardcoded user.

Status:
- Completed. The backend initializes SQLite automatically and persists board state for the hardcoded user.

Success criteria:
- A clear schema exists in docs.
- The database file is created automatically.

Verification:
- Inspect the database after startup.
- Validate the schema in docs.

### Part 6: Backend API

Tasks:
- Add routes for board read/update.
- Persist board state in SQLite.
- Add backend unit tests.

Status:
- Completed. The backend provides `/api/board` GET/PUT and persists state.

Success criteria:
- `GET /api/board` returns saved board state.
- `PUT /api/board` persists updates.

Verification:
- Backend tests for board endpoints.

### Part 7: Frontend/backend integration

Tasks:
- Fetch board state from the backend.
- Persist card moves, creates, deletes, and renames.
- Keep drag/drop working with API-backed state.

Status:
- Completed. The frontend consumes the backend board API and persists updates automatically.

Success criteria:
- Board state loads from backend.
- Changes persist after reload.

Verification:
- Integration tests for board persistence.
- End-to-end tests for board updates.

### Part 8: AI connectivity

Tasks:
- Add OpenRouter AI call support in the backend.
- Add a simple AI test route.
- Verify AI connectivity with a sample prompt.

Status:
- Completed. The backend now calls OpenRouter using `OPENROUTER_API_KEY` loaded from `.env`.

Success criteria:
- Backend successfully calls OpenRouter.
- The AI chat route returns a valid response.

Verification:
- AI connectivity test with `2+2`.

### Part 9: Structured AI responses

Tasks:
- Define an AI output schema with `message` and optional `boardUpdate`.
- Send board JSON and conversation context to the AI.
- Parse structured responses safely.

Status:
- Completed. AI responses can now include either a full board payload or action-based `boardUpdate` objects.

Success criteria:
- AI output is structured and parseable.
- Board updates are extracted reliably.

Verification:
- Backend tests for AI response parsing.

### Part 10: AI chat UI

Tasks:
- Add an AI chat sidebar in the frontend.
- Display conversation history and accept user prompts.
- Apply board updates from AI responses automatically.

Status:
- Completed. The AI chat panel now shows conversation history and applies board updates using `applyBoardUpdate()`.

Success criteria:
- The AI chat panel works.
- AI board updates refresh the UI.

Verification:
- End-to-end tests for chat with board updates.

### Part 11: Multi-user and multi-board support

Tasks:
- Replace browser-only authentication with backend login, registration, logout, and cookie session endpoints.
- Scope every board and AI request to the authenticated user.
- Migrate the SQLite `boards` table to include a board title and support multiple boards per user.
- Preserve the existing board as the default board for the original `user` account.
- Add board selection and board creation to the frontend.
- Update backend and frontend tests for accounts, ownership, and board switching.

Status:
- Completed (verified 2026-08-25). `backend/app/main.py` now exposes `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, and a session-checking `get_current_user` dependency that guards `/api/logout`, `/api/boards*`, and `/api/ai/chat`. `backend/app/db.py` scopes every board read/write by `user_id` in the SQL `WHERE` clause and supports a `title` per board with `list_boards`/`create_board`. The frontend `LoginForm.tsx` calls the real backend endpoints (register/login) instead of a local-only flag, and `KanbanBoard.tsx` adds a board picker and "Create board" form.

Success criteria:
- A newly registered user cannot read or update another user's boards. Met — `read_board`/`write_board` filter by `user_id`, and `backend/test/test_api.py::test_users_cannot_access_each_others_boards` covers this.
- A user can create and select more than one board, and changes persist to the selected board only. Met — `POST /api/boards`, board `<select>` in `KanbanBoard.tsx`, and `test_user_can_create_and_update_multiple_boards`.
- The existing `user` / `password` login and its existing board continue to work after migration. Met — `init_db()` seeds the default `user`/`password` account and its board on first run; `test_default_user_can_log_in_and_has_a_board` covers this.

Verification:
- Backend tests cover registration, login, ownership boundaries, and multi-board persistence (`backend/test/test_api.py`).
- Frontend tests cover board selection and creation (not yet confirmed for board-switching UI beyond existing `KanbanBoard.test.tsx` coverage — see Known issues).

## Known issues (from `review.md`, re-verified 2026-08-25)

An earlier code review (`review.md`, written against a pre-Part-11 checkout) is now partly stale — its two High findings about missing backend auth are fixed by Part 11. Re-verifying each finding against the current checkout:

- Fixed: backend had no auth on board/AI/logout routes -> now guarded by `get_current_user` (Part 11).
- Still live (Medium): `KanbanBoard.tsx`'s `persist()` still fires `void syncBoard(...)` without awaiting or serializing saves, so rapid edits can still complete out of order and silently overwrite a newer change with an older one; it does now check `response.ok` and surface a `loadError`, which the original review had flagged as missing.
- Still live (Medium): `backend/app/schemas.py`'s `AIResponse.boardUpdate` still accepts an arbitrary `dict[str, Any]`, and `frontend/src/lib/kanban.ts`'s `applyBoardUpdate()` still casts any object with `columns`/`cards` straight to `BoardData` with no invariant checks (unique ids, `cardIds` referencing real cards, etc.).
- Still live (Medium): the checked-in `backend/app/static` build is stale versus `frontend/src` (`index.html` dated 2026-08-05 12:02 predates `page.tsx`, `AIChatPanel.tsx`, `KanbanBoard.tsx`, and `LoginForm.tsx`, all modified later the same day) — running the backend directly from this checkout serves an outdated UI missing later changes until the Docker image is rebuilt.
- Still live (Medium): `frontend/tests/kanban.spec.ts` still navigates straight to `/` and asserts the "Kanban Studio" heading with no login step; given the current `page.tsx`, an unauthenticated session now renders `LoginForm` instead, so these tests do not exercise (and would not pass against) the authenticated app. Could not execute directly in this environment (Playwright's Chromium binary is not installed here), so this is a source-level finding, matching the original review's own limitation.
- Fixed: `npm run lint` now passes (exit code 0) — the `page.tsx` `set-state-in-effect` issue from the original review is resolved.
- Still live (Low): `Dockerfile` installs backend dependencies with plain `pip`; no `uv` project file or lockfile exists, contradicting the `uv` decision recorded in `AGENTS.md`.
- Still live (Low): `scripts/start.ps1` and `scripts/stop.ps1` still run `Set-ExecutionPolicy -Scope CurrentUser`, a persistent side effect unrelated to starting/stopping the app.
- Not re-verified: backend pytest was not runnable in this environment (no Python interpreter available), consistent with the original review's own note.

## Coding standards

- Use modern idiomatic code.
- Keep the implementation simple.
- Avoid unnecessary complexity.
- Fix root causes, not symptoms.

## Working documentation

All planning and execution documentation is in `docs/`.
Agent docs and the plan must be kept current before making code changes.
