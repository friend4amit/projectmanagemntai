# Code Review: Project Management MVP

**Date:** 2026-08-25
**Reviewer:** Automated code review
**Scope:** Full codebase review against `docs/PLAN.md` business requirements and coding standards

---

## Executive Summary

The project delivers a working local MVP with a Next.js frontend, FastAPI backend, SQLite persistence, and OpenRouter AI integration, all packaged in a single Docker container. The code is well-structured, compact, and idiomatic. Separation of concerns is clear across frontend, backend, and infrastructure layers. Authentication, multi-user/multi-board support, and structured AI responses are all implemented. The primary gaps are around save race conditions, AI response validation, testing coverage, and a few tooling mismatches. None are blocking for local MVP use; all should be addressed before any production deployment.

---

## 1. Architecture Review

The architecture is a sound choice for a local MVP:

- **Frontend:** Next.js in static export mode (`output: "export"`) eliminates the need for a Node.js runtime in production. The built HTML/JS/CSS is served by FastAPI. This is a clean deployment model for a single-container app.
- **Backend:** FastAPI handles all API routes, authentication, database access, AI calls, and static file serving. The SPA fallback pattern correctly routes unmatched paths to `index.html`.
- **Database:** SQLite with a JSON blob for board state is pragmatic for an MVP. It avoids relational complexity while still supporting multi-user ownership.
- **AI Integration:** OpenRouter via a system+user prompt with structured JSON output is well-suited. The brace-matching JSON extraction is fragile but workable.
- **Containerization:** Multi-stage Docker build (Node for frontend, Python for runtime) keeps the final image lean.

**Concerns:**
- The static export means no SSR, no API routes, no middleware, and no `next/image` optimization. This is intentional and documented, but limits future extensibility.
- Board state as a single JSON blob prevents atomic partial updates and makes concurrent writes fragile.

---

## 2. Backend Review

### 2.1 Authentication

**Files:** `backend/app/main.py`, `backend/app/db.py`

- Password hashing uses PBKDF2-HMAC-SHA256 with 600,000 iterations and a random 16-byte salt. Verification uses `hmac.compare_digest` for timing-safe comparison. This is solid.
- Sessions are cookie-based (`pm_session`), stored in an in-memory `dict[str, int]`. Token is `secrets.token_urlsafe(32)`. Cookie is `httponly=True`, `samesite="lax"`.
- The `get_current_user` dependency correctly guards all board and AI routes.
- Board operations are scoped by `WHERE user_id = ?` in SQL, preventing cross-user access (verified by `test_users_cannot_access_each_others_boards`).

**Issues:**
- In-memory sessions are lost on every container restart. Acceptable for local MVP but should be documented.
- Cookie is not set to `secure=True`. Fine for local HTTP but must be set before HTTPS deployment.
- No CSRF protection. `SameSite=Lax` provides partial protection for GET/safe methods, but POST endpoints (logout, board updates, AI chat) have no CSRF token.
- Default credentials `user`/`password` are hardcoded in `db.py:11` and visible in `LoginForm.tsx` UI. Should be removed or made configurable before non-local deployment.

### 2.2 API Routes

**File:** `backend/app/main.py`

10 endpoints are defined with a clean REST-like structure:

| Endpoint | Auth | Purpose |
|----------|:---:|---------|
| `GET /api/ping` | No | Health check |
| `POST /api/auth/register` | No | Create account |
| `POST /api/auth/login` | No | Authenticate |
| `GET /api/auth/me` | Yes | Current user |
| `POST /api/logout` | Yes* | Destroy session |
| `GET /api/boards` | Yes | List user boards |
| `POST /api/boards` | Yes | Create board |
| `GET /api/boards/{id}` | Yes | Read board |
| `PUT /api/boards/{id}` | Yes | Update board |
| `POST /api/ai/chat` | Yes | AI chat |

*Logout reads the cookie but does not enforce authentication -- silently does nothing if no session exists.

**Issues:**
- No rate limiting on any endpoint, including the AI chat endpoint which makes external API calls.
- No logging anywhere in the backend. Authentication failures, database errors, and AI call failures are all silent.
- `init_db()` is called at startup via lifespan but also redundantly inside `create_user()` and `authenticate_user()`. The `CREATE TABLE IF NOT EXISTS` pattern makes this safe but wasteful.

### 2.3 Database

**File:** `backend/app/db.py`

- Two tables: `users` (id, username, password) and `boards` (id, user_id, title, data, created_at, updated_at).
- Migration logic checks for a missing `title` column and issues `ALTER TABLE ADD COLUMN` if absent. Simple and functional.
- Default seed creates `user`/`password` account with a 5-column, 8-card board on first startup.

**Issues:**
- Every database function creates its own connection and closes it explicitly. No context manager or connection pooling. Functions like `authenticate_user`, `list_boards`, `read_board`, and `write_board` do not use `try/finally` -- if an exception occurs between `get_connection()` and `connection.close()`, the connection leaks.
- `check_same_thread=False` is set to allow FastAPI's threadpool to share the connection. Works but SQLite is not designed for concurrent writes.
- All database calls are synchronous. FastAPI runs them in a threadpool so they do not block the event loop, but this is not the most efficient pattern.

### 2.4 AI Integration

**File:** `backend/app/ai.py`

- Calls OpenRouter via synchronous `urllib.request` with a 30-second timeout.
- Constructs a system message defining the AI role and board-update schema, plus a user message with the prompt and full board JSON.
- Response parsing uses a brace-matching heuristic (`find("{")` / `rfind("}")`) to extract JSON from the AI response text.

**Issues:**
- The `AIResponse.boardUpdate` schema accepts `dict[str, Any]` as a fallback, defeating Pydantic validation for that field. Any dict passes through.
- AI board updates are returned to the client but not validated against board invariants (unique IDs, card references, etc.) before being sent.
- The synchronous `urllib.request` blocks a thread for up to 30 seconds per AI call.
- The hand-rolled `.env` parser (`_load_dotenv_if_present`) is a pragmatic choice but has no quoting/escaping support.

### 2.5 Code Quality

- `requirements.txt` lists `httpx2>=0.4.0` but it is never imported. Unused dependency.
- No logging framework configured. Errors are swallowed silently.
- `create_user` and `authenticate_user` both call `init_db()` before their main logic, adding unnecessary overhead on every auth operation.

---

## 3. Frontend Review

### 3.1 Component Architecture

**Files:** `frontend/src/components/`, `frontend/src/app/page.tsx`

The component hierarchy is clean and well-organized:

```
page.tsx (auth gate)
  +-- LoginForm (login/register)
  +-- KanbanBoard (board container)
        +-- KanbanColumn (x5, droppable)
        |     +-- KanbanCard (sortable)
        |     +-- NewCardForm (inline add)
        +-- AIChatPanel (sidebar)
```

State management uses React `useState`/`useRef` exclusively -- no external state library. This is appropriate for the app's complexity. Data flows parent-to-child via props and child-to-parent via callbacks.

**Issues:**
- `KanbanBoard.tsx` (170 lines) is dense. Several handlers are single-line arrow functions with deeply nested spread operations that hurt readability.
- `page.tsx` is a `"use client"` component that handles both auth gating and layout. The session restore logic is clean but could be extracted into a custom hook for clarity.

### 3.2 Kanban Board

**Files:** `KanbanBoard.tsx`, `KanbanColumn.tsx`, `KanbanCard.tsx`, `kanban.ts`

- Drag-and-drop uses `@dnd-kit` with `PointerSensor` (6px activation distance), `closestCorners` collision detection, and `verticalListSortingStrategy`. This is a solid, well-configured setup.
- The `moveCard` function handles same-column reorder, cross-column move (on card), and cross-column move (on column header). Logic is correct and tested.
- Board data uses a normalized model: cards in a flat `Record<string, Card>`, columns reference card IDs. This avoids duplication and makes moves efficient.
- Persistence uses a `saveQueue` ref to serialize async `PUT` requests.

**Issues:**
- **Column rename fires `persist()` on every keystroke** (`onChange` handler). Each keystroke triggers both a `setBoard` call and a `PUT /api/boards/:id` network request. This should be debounced or use `onBlur`.
- **No-op `useMemo`** at line 113: `useMemo(() => board.cards, [board.cards])` returns the same reference with the same dependency -- it provides no memoization benefit.
- **No optimistic concurrency / conflict resolution.** The save queue serializes network calls, but there is no versioning or ETag-based conflict detection. Rapid edits can still result in an older state overwriting a newer one if the server processes them out of order.

### 3.3 AI Chat Panel

**File:** `AIChatPanel.tsx`, `kanban.ts:applyBoardUpdate`

- Sends prompts to `POST /api/ai/chat` and displays responses in a message list.
- `applyBoardUpdate` handles multiple action formats: full board replacement, `createCard`, `renameColumn`, and `moveCard`.
- `isValidBoardData` validates structural correctness (array types, unique column IDs, card references).

**Issues:**
- Full board replacement from AI is trusted without checking against current state (e.g., preserving existing card IDs).
- `isValidBoardData` does not check that every `cardId` in columns exists in `cards`, or that cards occur exactly once. (Partial fix exists but is incomplete.)
- No test coverage for `applyBoardUpdate` despite its complexity and multiple code paths.

### 3.4 Styling

- Tailwind CSS v4 with a custom design system via CSS variables (`--accent-yellow`, `--primary-blue`, `--secondary-purple`, `--navy-dark`, `--gray-text`).
- Fonts: Manrope (body) and Space Grotesk (display) via `next/font/google`.
- `clsx` used for conditional class merging. Consistent `rounded-2xl`/`rounded-3xl` patterns. Some glassmorphism touches (`bg-white/80`, `backdrop-blur`).
- The design system is clean and consistently applied.

### 3.5 API Layer

**File:** `frontend/src/lib/api.ts`

- `apiFetch` wrapper prepends `http://localhost:8000` in development and uses empty base in production (same-origin). Always sets `credentials: "include"`.
- Error handling checks `response.ok` and surfaces errors via component state.
- A global error banner displays board load/save failures.

**Issues:**
- `createId` in `kanban.ts` uses `Math.random()` for ID generation. Not cryptographically secure and could theoretically produce collisions. `crypto.randomUUID()` would be better.
- No input sanitization on card titles, column titles, or chat prompts. React auto-escapes HTML in text nodes so XSS via rendering is not a concern, but downstream consumers should be aware.

---

## 4. Infrastructure Review

### 4.1 Dockerfile

**File:** `Dockerfile`

- Two-stage build: `node:20-alpine` builds the frontend, `python:3.12-slim` runs the backend.
- Frontend is built with `npm ci` + `npm run build` and copied to `app/static/`.
- Backend dependencies installed via `pip install --no-cache-dir -r requirements.txt`.

**Issues:**
- **Does not use `uv` as specified** in `AGENTS.md` and `docs/PLAN.md`. The `Dockerfile:13` installs with `pip`. No `pyproject.toml` or lockfile exists. This contradicts the stated technical decision.
- No `.dockerignore` exclusion for `frontend/out/` or `frontend/.next/` -- these could be copied unnecessarily during build context transfer.

### 4.2 Scripts

**Files:** `scripts/start.ps1`, `scripts/stop.ps1`, `scripts/start.sh`, `scripts/stop.sh`

- Cross-platform start/stop scripts for Docker.
- Start scripts build the image and run the container with `--env-file .env`.

**Issues:**
- `scripts/stop.ps1:5` runs `Set-ExecutionPolicy -Scope CurrentUser`, a persistent side effect unrelated to stopping the app. Should be removed.
- `scripts/start.ps1` does not have the same execution policy line, so `stop.ps1` is inconsistent.

### 4.3 Static Build

- `backend/app/static/` is gitignored (correct) but may be stale if someone runs the backend directly without Docker. The Dockerfile regenerates it during build.
- The checked-in build artifact in the repo was found to be stale in the earlier `review.md` review (dated 2026-08-05 predating later source changes). Running the backend from checkout without Docker serves an outdated UI.

---

## 5. Testing Review

### 5.1 Backend Tests

**File:** `backend/test/test_api.py`

7 tests covering:
- Health check (`test_ping`)
- Login (`test_default_user_can_log_in`)
- Registration (`test_registration_and_login`)
- Multi-board CRUD (`test_user_can_create_and_update_multiple_boards`)
- User isolation (`test_users_cannot_access_each_others_boards`)
- Logout (`test_logout`)
- Path traversal (`test_static_fallback_rejects_path_traversal`)

**Gaps:**
- No test for the AI endpoint (`/api/ai/chat`).
- No test for duplicate username registration (409 conflict).
- No test for invalid credentials (401 on login).
- No test for PUT with invalid board data (schema validation).

### 5.2 Frontend Unit Tests

**Files:** `KanbanBoard.test.tsx`, `kanban.test.ts`

- `kanban.test.ts`: 3 tests for `moveCard` (same-column reorder, cross-column move, drop-to-column-end).
- `KanbanBoard.test.tsx`: Tests for rendering, column rename, card add/remove, board create/select.

**Gaps:**
- No tests for `applyBoardUpdate` despite its complexity and 4 distinct code paths.
- No tests for `isValidBoardData`.
- No tests for `LoginForm` (login/register toggle, error display, form validation).

### 5.3 E2E Tests

**File:** `tests/kanban.spec.ts`

Playwright tests for board load, card add, drag-and-drop, logout, and invalid login.

**Issues:**
- Tests navigate directly to `/` without performing login first. With the current auth-gated `page.tsx`, these tests would render `LoginForm` instead of the Kanban board, causing assertions on "Kanban Studio" to fail.
- Tests use Playwright but Chromium was not installed in the environment, so they could not be executed for verification.

---

## 6. Security Review

| Area | Status | Notes |
|------|--------|-------|
| Password hashing | Good | PBKDF2-SHA256, 600k iterations, random salt, timing-safe compare |
| Session management | Acceptable | Cookie-based, httponly, samesite=lax. In-memory storage lost on restart |
| Cookie security | Needs work | Not `secure=True`; fine for local HTTP, must be set for HTTPS |
| CSRF protection | Missing | No CSRF tokens. Partially mitigated by SameSite=Lax |
| Path traversal | Protected | `is_relative_to()` check on static file paths, verified by test |
| Input sanitization | Acceptable | React auto-escapes HTML in text nodes. No `dangerouslySetInnerHTML` usage |
| AI response validation | Weak | `boardUpdate` accepts arbitrary dict. `isValidBoardData` is partial |
| Hardcoded credentials | Documented risk | `user`/`password` in source code and UI. MVP limitation |
| API key exposure | Good | `OPENROUTER_API_KEY` in `.env` (gitignored), passed via `--env-file` |

---

## 7. Findings Summary

### Medium Severity

| # | Finding | Location | Recommended Fix |
|---|---------|----------|-----------------|
| M1 | Concurrent saves can overwrite newer board edits; save queue serializes but has no conflict detection | `KanbanBoard.tsx:persist()` | Add revision/ETag tracking or debounce saves; surface failures to user |
| M2 | AI `boardUpdate` not validated for board invariants (unique IDs, card references) before client-side application | `schemas.py:AIResponse`, `kanban.ts:applyBoardUpdate` | Use discriminated action schema; validate invariants on server before returning |
| M3 | Stale static build in `backend/app/static/` serves outdated UI when running backend directly | `backend/app/static/` | Do not commit build artifacts; rely on Dockerfile to regenerate |
| M4 | E2E tests bypass authentication; will fail against current auth-gated UI | `tests/kanban.spec.ts:3-6` | Add login step in `beforeEach`; add positive/negative login tests |

### Low Severity

| # | Finding | Location | Recommended Fix |
|---|---------|----------|-----------------|
| L1 | Dockerfile uses `pip`, not `uv` as specified in technical decisions | `Dockerfile:13` | Add `pyproject.toml`, install `uv` in Docker image, use `uv pip install` |
| L2 | `scripts/stop.ps1` sets persistent `Set-ExecutionPolicy` | `scripts/stop.ps1:5` | Remove the line; document `powershell -ExecutionPolicy Bypass` as alternative |
| L3 | Unused `httpx2` dependency in `requirements.txt` | `requirements.txt` | Remove `httpx2>=0.4.0` from requirements |
| L4 | `init_db()` called redundantly on every auth operation | `db.py:create_user`, `db.py:authenticate_user` | Call `init_db()` once at startup only |
| L5 | DB connections not protected by `try/finally` in several functions | `db.py:authenticate_user`, `list_boards`, `read_board`, `write_board` | Wrap connection usage in `try/finally` blocks |
| L6 | Column rename fires `persist()` on every keystroke (no debounce) | `KanbanColumn.tsx:onChange` | Debounce the rename or use `onBlur` handler |
| L7 | No-op `useMemo` returns `board.cards` with `board.cards` as dependency | `KanbanBoard.tsx:113` | Remove the memo or replace with a meaningful computation |
| L8 | `createId` uses `Math.random()` instead of cryptographically secure RNG | `kanban.ts:createId` | Use `crypto.randomUUID()` |
| L9 | No logging anywhere in the backend | All backend files | Add structured logging for auth, DB, and AI operations |
| L10 | Deprecated `export` script in `package.json` (`next export`) | `frontend/package.json` | Remove the `"export"` script; static export is handled by `next build` with `output: "export"` |

### Informational

| # | Finding | Location |
|---|---------|----------|
| I1 | No tests for AI endpoint, `LoginForm`, or `applyBoardUpdate` | Various |
| I2 | In-memory sessions lost on container restart | `main.py:sessions` |
| I3 | Default credentials hardcoded in source and visible in UI | `db.py:11`, `LoginForm.tsx` |
| I4 | Synchronous AI call blocks thread for up to 30 seconds | `ai.py:call_openrouter` |
| I5 | `check_same_thread=False` on SQLite allows cross-thread access | `db.py:get_connection` |
| I6 | No `aria-live` regions for dynamic content (AI messages, errors) | `AIChatPanel.tsx`, `KanbanBoard.tsx` |
| I7 | No confirmation dialog before card deletion | `KanbanCard.tsx` |
| I8 | No loading states for board creation and card creation | `KanbanBoard.tsx`, `NewCardForm.tsx` |

---

## 8. Conclusion

This is a well-structured, cleanly written MVP. The code is idiomatic, the architecture is sound, and the core features (authentication, multi-user boards, drag-and-drop Kanban, AI chat with board updates) are all functional. The separation between frontend, backend, and infrastructure is clear.

The most important items to address before considering this ready for handoff or any shared use are:

1. **Save race condition (M1):** The column-rename-on-keystroke pattern combined with fire-and-forget saves means data loss is possible with rapid edits.
2. **AI response validation (M2):** An imperfect AI response can corrupt the board state. The server should validate before returning.
3. **E2E test fix (M4):** The tests do not exercise the authenticated app and will fail in their current state.

The low-severity items (uv migration, connection management, debouncing, logging) are worth addressing incrementally but are not blocking for local MVP use.

**Overall assessment:** The project is a solid foundation. With the medium-severity items resolved, it would be ready to hand off for further development or limited shared use.
