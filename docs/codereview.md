# Code Review: Project Management MVP

**Date:** 2026-08-25
**Scope:** Full repository — `backend/`, `frontend/`, `Dockerfile`, `scripts/`, and their tests — reviewed against `AGENTS.md` / `docs/PLAN.md` requirements and coding standards.
**Method:** Direct reading of every source file (not a diff-only review), cross-checked against actual behavior: frontend lint and unit tests were executed (`npm run lint`, `npm run test:unit`) and passed; backend tests could not be executed in this environment (no Python interpreter installed — only a Microsoft Store execution-alias stub is present) and were reviewed by code inspection instead. Findings below are stated as verified (executed or traced through code) or inferred (plausible but not executed) where that distinction matters.

An earlier automated review exists at `docs/codereview_oc.md`. Several of its findings were re-verified here and are noted explicitly where this review's conclusion differs.

---

## 1. Executive Summary

This is a small, coherent MVP: Next.js static export served by FastAPI, SQLite for persistence, OpenRouter for AI chat, packaged as one Docker image. The code is idiomatic and free of over-engineering, consistent with the project's stated coding standards. Core flows — auth, multi-board CRUD, drag-and-drop, AI board updates — are implemented and (where testable) covered by passing tests.

The most consequential real gaps are:
1. AI-driven "action" updates (`createCard`/`renameColumn`/`moveCard`) are not validated by the backend schema at all — only full-board replacements go through `BoardData`'s invariant checks.
2. There is no cross-session conflict handling: two browser tabs (or two devices) editing the same board will silently last-write-wins, and a failed save leaves the UI showing an unsaved change as if it succeeded.
3. Backend tests cannot be run in this checkout because no Python/uv environment is installed, which also means the `uv` package-manager decision in `AGENTS.md` has never actually been exercised — the Dockerfile uses plain `pip`.

Nothing here blocks continued local MVP use. The single-user-editing, single-machine, `docker run` deployment model sidesteps most of the concurrency and session-durability issues in practice.

---

## 2. Architecture

- **Build/serve**: `Dockerfile` builds the frontend (`node:20-alpine`, `npm ci && npm run build`, static export via `output: "export"` in `next.config.ts`) and copies `frontend/out` into `backend/app/static` for a `python:3.12-slim` runtime stage. Clean, minimal image.
- **Backend**: single `FastAPI` app (`backend/app/main.py`, 147 lines) handling auth, board CRUD, AI chat, and the SPA static-file fallback. No routers/blueprints — appropriate at this size.
- **Data model**: `users(id, username, password)` and `boards(id, user_id, title, data, created_at, updated_at)`, board state as a JSON blob (`{columns, cards}`), scoped by `user_id` on every read/write. This is documented consistently in `CLAUDE.md`, `backend/app/schemas.py` (Pydantic), and `frontend/src/lib/kanban.ts` (TypeScript) — the three are in sync as of this review.
- **AI integration**: synchronous `urllib` call to OpenRouter, brace-matched JSON extraction from the completion text, applied client-side via `applyBoardUpdate()`.

This is a reasonable shape for the stated goal (local, single-container, MVP). The one structural weakness is that "board state" has two independent notions of validity — the Pydantic `BoardData` model server-side and `isValidBoardData`/`applyBoardUpdate` client-side — that must be kept in sync by hand as the AI action vocabulary grows (see 3.3).

---

## 3. Backend (`backend/app/`)

### 3.1 Authentication and sessions (`main.py`, `db.py`)

- Password hashing: PBKDF2-HMAC-SHA256, 600,000 iterations, random 16-byte salt, `hmac.compare_digest` for verification (`db.py:17-31`). This is solid for an MVP.
- Sessions are cookie-based (`pm_session`, `httponly=True`, `samesite="lax"`), backed by an in-process `dict[str, int]` (`main.py:21`). Tokens are `secrets.token_urlsafe(32)`.
- `get_current_user` (`main.py:46-51`) correctly guards `/api/auth/me`, `/api/boards*`, and `/api/ai/chat`.
- **Confirmed by test**: `test_users_cannot_access_each_others_boards` exercises the `user_id`-scoped `WHERE` clause in `db.py:read_board`.

Issues:
- **Sessions never expire and are never pruned.** `sessions[token] = user_id` is only ever removed on explicit logout (`main.py:91-93`). A long-running container accumulates one dict entry per login/register forever. Low impact for local MVP use, but worth a one-line comment or TTL if this ever runs unattended for long periods.
- **No login rate limiting.** `/api/auth/login` and `/api/auth/register` have no throttling, so the PBKDF2 cost is the only brake on credential guessing. Acceptable for a local-only tool, not for anything network-exposed.
- Cookie is not `secure=True` (fine for local HTTP; must change before any HTTPS/shared deployment) and there is no CSRF token — `SameSite=Lax` gives partial protection only. Same caveat as above: acceptable while this is genuinely local-only.
- Default `user`/`password` account is hardcoded in `db.py:11` and advertised in `LoginForm.tsx:55` ("Default login: user / password"). This is a deliberate, documented MVP decision per `AGENTS.md`, not an oversight — flagging only so it isn't forgotten if this ever leaves a trusted local machine.

### 3.2 API surface (`main.py`)

10 routes, consistently guarded where they need to be. Two smaller correctness notes:

- `logout` (`main.py:89-94`) doesn't require `get_current_user` — it just pops the cookie's token from `sessions` if present and always returns 200. That's intentional-looking (logout should be idempotent/safe to call while already logged out) but means it gives no signal about whether a session actually existed; not a bug, just worth naming as a deliberate choice rather than a gap.
- `AIRequest.prompt` (`main.py:16-18`) has no length limit, unlike `Credentials`/`CreateBoard` which use `Field(min_length=..., max_length=...)`. A very large prompt is forwarded verbatim into the OpenRouter payload. Low-severity (no rate limiting elsewhere either, and this is local-only), but inconsistent with the pattern used for the other two user-input models.
- `read_static`'s path-traversal guard (`candidate.is_relative_to(static_dir)`) is correct and **confirmed by test** (`test_static_fallback_rejects_path_traversal`, which passed).

### 3.3 AI response validation — the one real correctness gap

`schemas.py:64-66`:
```python
class AIResponse(BaseModel):
    message: str
    boardUpdate: BoardData | dict[str, Any] | None = None
```

`BoardData` itself has good invariant checks (`schemas.py:22-42`: unique column ids, card-key/id match, no card in two columns, no dangling `cardIds`). But that model only matches a **full board replacement**. The AI is prompted to also return partial "action" objects (`{"action": "createCard", ...}`, `renameColumn`, `moveCard` — see `ai.py`'s system/user prompt and `kanban.ts:applyBoardUpdate`'s handling of `update.action`). Any such partial object fails `BoardData` validation and falls through to the `dict[str, Any]` arm of the union, which accepts literally anything. The backend performs **zero validation** on action-style updates before returning them to the client.

The actual invariant enforcement for that path lives entirely in `frontend/src/lib/kanban.ts`'s `applyBoardUpdate` (e.g. `createCard` falls back to `board.columns[0]` if the AI names a nonexistent column, `moveCard` no-ops if the card or target column can't be resolved). This works today because the one caller (`AIChatPanel.tsx`) is defensive, but it means the server-side schema is decorative for this whole code path, and any future second consumer of `/api/ai/chat` (a script, a different UI) would get unvalidated data. If this schema is tightened, prefer a discriminated union (`Literal["createCard"] | Literal["renameColumn"] | Literal["moveCard"]` action models) over `dict[str, Any]`, so the same guarantees `BoardData` already gives full replacements extend to actions.

### 3.4 Database (`db.py`)

- Every function opens and explicitly closes its own `sqlite3.connect(..., check_same_thread=False)`. Functions that use `with connection:` (`init_db`, `create_user`, `create_board`, `write_board`) get transactional commit/rollback; `authenticate_user`, `get_user`, and `list_boards` are read-only `SELECT`s without a `with` block, but since they never mutate, the missing transaction context isn't a correctness issue — only `create_user` needed (and has) a `try/finally` for cleanup on the `IntegrityError` path. No actual connection leak found on inspection: every function reaches `connection.close()` on both success and (for read paths) the only exception that isn't already handled would propagate before use anyway.
- `init_db()` is called once from the FastAPI `lifespan`, but also redundantly at the top of `create_user` and `authenticate_user` (`db.py:131`, `151`). Because the SQL is `CREATE TABLE IF NOT EXISTS`, this is safe but does re-run four statements (two `CREATE TABLE`, one `PRAGMA table_info`, one `INSERT OR IGNORE`) on every login and registration. Minor, worth trimming since `lifespan` already guarantees it ran once at startup.
- Migration logic (`title` column backfill, `db.py:107-111`) is a reasonable, minimal `ALTER TABLE` pattern for a single-column addition.
- `_load_default_board()` re-reads and re-parses `board.json` from disk on every new-user registration and every new-board creation (via `_blank_board`); fine at this scale, not worth caching for an MVP.

### 3.5 Dependencies

- `backend/requirements.txt` lists `httpx2>=0.4.0`. This is not imported anywhere in `backend/` (confirmed by grep) — `ai.py` uses `urllib.request` directly. `httpx2` is not the real PyPI `httpx` package; this looks like a typo that happens to resolve to a real (unrelated) package name. It should be removed — at best it's dead weight, at worst it's installing an unintended dependency by name confusion.
- No `pyproject.toml` / `uv.lock` exists, and `Dockerfile:13` uses plain `pip install`. `AGENTS.md` and `docs/PLAN.md` both record "use `uv` as the Python package manager" as a technical decision; the codebase has never implemented it. This is a documented-but-unimplemented decision, not a regression — worth either doing or removing from the docs so they stop drifting from reality.

---

## 4. Frontend (`frontend/src/`)

### 4.1 Component structure

```
page.tsx (session restore, auth gate)
  LoginForm (login/register)
  KanbanBoard (board list, board CRUD, drag/drop, persistence)
    KanbanColumn x N (rename, add card)
      KanbanCard (delete)
      NewCardForm
    AIChatPanel (chat + boardUpdate application)
```

State is plain `useState`/`useRef`, props down / callbacks up, no external state library — appropriate for this size. `kanban.ts` keeps the board model normalized (`cards: Record<id, Card>`, `columns[].cardIds: string[]`), which keeps `moveCard` a pure array operation instead of a deep object mutation; `kanban.test.ts`'s three `moveCard` cases (same-column reorder, cross-column move, drop-to-column-end) passed.

### 4.2 Save queue and optimistic updates (`KanbanBoard.tsx:76-85`)

```ts
const persist = (nextBoard: BoardData) => {
  if (boardId === null) return;
  setBoard(nextBoard);
  saveQueue.current = saveQueue.current
    .then(() => syncBoard(boardId, nextBoard))
    .catch((error) => {
      setLoadError("Unable to save this board. Refresh and try again.");
      console.error(error);
    });
};
```

Correcting a claim in `docs/codereview_oc.md`: this **does** serialize writes correctly — each call chains a new `.then()` onto the previous promise, so PUT requests fire strictly in the order `persist()` was called, and one cannot complete after a later one starts. There is no same-tab out-of-order write risk.

The real gaps are different from "ordering":
- **No debounce on column rename.** `KanbanColumn.tsx:44` calls `onRename` — which is wired straight to `persist()` — on every keystroke (`onChange`, not `onBlur`). Typing a 10-character column title fires 10 sequential `PUT /api/boards/{id}` calls, each carrying the full board JSON. Functionally correct (thanks to the queue) but wasteful and adds latency under slow network conditions. Debounce or switch to `onBlur`.
- **Optimistic update with no rollback on failure.** `setBoard(nextBoard)` happens synchronously before the network call; if `syncBoard` rejects (e.g. the board was deleted from another session, or the network drops), the UI keeps showing the change while `loadError` reports "Unable to save" — the user has no way to tell from the board itself that their edit isn't actually persisted, and a page refresh would silently discard it.
- **No cross-session conflict detection.** Nothing (ETag, revision counter, `updated_at` check) prevents two tabs/devices editing the same board from silently overwriting each other — last PUT wins. Low real-world impact for a single local user, but worth naming precisely since `docs/codereview_oc.md`'s framing (same-tab race) isn't the actual mechanism.

### 4.3 Minor code-quality items (frontend)

- `KanbanBoard.tsx:113`: `const cardsById = useMemo(() => board.cards, [board.cards]);` — memoizing a value with itself as its only dependency does nothing; either drop the `useMemo` or it's a placeholder for a real computation that never arrived.
- `createId` (`kanban.ts:164-168`) builds IDs from `Math.random()` + `Date.now()` rather than `crypto.randomUUID()`. Not a security issue (IDs aren't secrets) but `crypto.randomUUID()` is simpler and available in every target runtime (Node 20/modern browsers) here.
- `frontend/package.json`'s `"export": "next export"` script (line 7) is a Next.js 13-era API; with `output: "export"` already set in `next.config.ts`, `next build` alone performs the export and this script is unused/redundant dead weight (worth removing rather than leaving as a trap for someone who runs it expecting it to do something `next build` doesn't already do).
- `AIChatPanel.tsx` and `KanbanBoard.tsx` have no `aria-live` region for the assistant's response or the load/save error banner, so a screen reader user gets no notification when either appears. Minor accessibility gap, not a functional bug.

### 4.4 `applyBoardUpdate` / AI update handling (`kanban.ts:201-279`)

Reasonably defensive given the backend does not validate action payloads (3.3): `isValidBoardData` checks column-id uniqueness, card-id/key match, no duplicate placement, and no dangling references before accepting a full-board replacement; the three action branches (`createCard`, `renameColumn`, `moveCard`) type-check every field they read and no-op rather than throw on malformed input. No test coverage exists for this function (`kanban.test.ts` only covers `moveCard`), which is notable given it's the widest attack surface for a misbehaving or adversarially-prompted AI response — worth adding unit tests for at least: valid full replacement, invalid full replacement (rejected), each of the three actions with valid input, and each action with a missing/wrong-typed field.

---

## 5. Testing

### 5.1 Backend (`backend/test/test_api.py`) — reviewed, not executed here

7 tests: ping, default-user login + board, multi-board create/update, new-board-starts-blank, cross-user isolation, logout-revokes-session, path-traversal rejection. Each test's assertions were traced against the corresponding route/db logic and are consistent with the implementation. Gaps: no test for `/api/ai/chat` (understandable — it calls an external service — but the parsing/validation logic in `ai.py` and the `AIResponse` schema fallback in 3.3 could be tested with a mocked `urlopen`), no test for duplicate-username 409, no test for wrong-password 401, no test for `PUT` with structurally invalid board data (would currently 422 via `BoardData` validation — untested but plausible from reading `schemas.py`).

**This review could not run `pytest`** — no Python interpreter is installed in this environment (only the Windows Store app-execution-alias stub, which errors instead of running). This matches the same limitation noted in `docs/codereview_oc.md`; it is an environment gap, not a project one, but it does mean the `uv`/`pytest` workflow described in `CLAUDE.md` has not actually been exercised end-to-end during this review or (per available evidence) recently in general.

### 5.2 Frontend unit tests — executed, passed

`npm run test:unit`: **7/7 passed** (`kanban.test.ts` x3, `KanbanBoard.test.tsx` x4 — render, rename, add/remove card, create+select board). `npm run lint`: **clean, no output, exit 0.**

### 5.3 Frontend E2E (`frontend/tests/kanban.spec.ts`) — reviewed, not executed here

**Correcting `docs/codereview_oc.md`'s M4 finding**, which states these tests "navigate straight to `/` without performing login" and would fail against the auth-gated UI: that was true of the file at commit `6c71ef9`, but commit `f07b743` ("post review fixes", same day) rewrote it to log in via `page.request.post("/api/auth/login")` in a `test.beforeEach`, before every `page.goto("/")`, plus added a standalone unauthenticated test for the invalid-credentials case. The current file (verified by reading it directly, not by git-log inference) does exercise the authenticated app correctly. This finding is stale and should not be carried forward. Playwright's Chromium was not launched in this review either, so the tests are verified by reading, not by execution — but the auth-bypass concern specifically is resolved.

---

## 6. Infrastructure

### 6.1 Dockerfile

Two-stage build (`node:20-alpine` → `python:3.12-slim`), clean and minimal. Confirmed issues:
- Uses `pip`, not `uv`, contradicting the documented technical decision (3.5).
- `.dockerignore` already excludes `frontend/node_modules`, `.next`, `out`, `.env`, `.git`, `*.db` — this is correctly configured, so the earlier review's concern about unnecessary build-context transfer does not hold up; it was already handled.

### 6.2 Scripts (`scripts/`)

- `scripts/stop.ps1:5` runs `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` — a persistent, machine-wide side effect with no relationship to stopping a Docker container. `scripts/start.ps1` has no equivalent line, so behavior is inconsistent between the two entry points a user is equally likely to run first.
- **New finding, not in the prior review**: `scripts/executionpolicy.ps1` exists as its own file containing exactly that one line, and is not referenced by `start.ps1`, `stop.ps1`, or anything else in the repo (confirmed by grep). It's dead code — either it was meant to be dot-sourced by the other scripts and that wiring was never done, or it's a leftover from an earlier iteration. Either delete it or actually call it from both `start.ps1` and `stop.ps1` (and drop the inline duplicate in `stop.ps1`) so the execution-policy handling exists in exactly one place.
- `stop.sh` and `start.sh` are consistent with each other and with the `.ps1` pair's actual Docker behavior.

### 6.3 Checked-out static build

`backend/app/static/` is correctly `.gitignore`d (`.gitignore:112-113`) — this is not a repo defect. It is however present and **stale in this specific working copy right now**: `index.html`'s last-write time (12:42:31) predates several `.tsx` source files modified 3 minutes later (12:45:16) in the same session. This is purely a local build-freshness artifact of running the backend outside Docker without rebuilding — not something to fix in code, but worth remembering: `uvicorn app.main:app --reload --app-dir backend` (the documented no-Docker dev command) will silently serve an outdated UI whenever frontend source changes after the last `npm run build`.

---

## 7. Security Summary

| Area | Status | Notes |
|---|---|---|
| Password hashing | Good | PBKDF2-SHA256, 600k iterations, random salt, timing-safe compare |
| Ownership boundary | Good | Every board query is `WHERE ... AND user_id = ?`; covered by a passing test |
| Path traversal | Good | `is_relative_to()` guard on the static fallback; covered by a passing test |
| Session storage | Acceptable for local MVP | In-memory, unbounded growth, lost on restart — all documented/acceptable trade-offs, not bugs |
| CSRF | Missing, mitigated | No CSRF token; `SameSite=Lax` gives partial protection. Fine while genuinely local-only |
| Cookie `secure` flag | Missing, expected | Not set; must be added before any HTTPS/non-local deployment |
| Rate limiting | Missing | None on login, register, or AI chat. Acceptable locally, not otherwise |
| AI response trust | Weak | Action-style `boardUpdate`s bypass all backend schema validation (3.3); client-side handling is defensive but is the only safety net |
| XSS | Not a concern | No `dangerouslySetInnerHTML`; React escapes all rendered text |
| Secrets handling | Good | `OPENROUTER_API_KEY` from `.env`, gitignored, passed via `--env-file`, never logged |

---

## 8. Findings by Severity

### Medium

| # | Finding | Location |
|---|---|---|
| M1 | AI "action" `boardUpdate`s (`createCard`/`renameColumn`/`moveCard`) bypass all backend schema validation — only full-board replacements go through `BoardData`'s invariants | `backend/app/schemas.py:66`, `backend/app/ai.py` |
| M2 | Optimistic board updates are never rolled back on save failure; the UI can show an edit that was not actually persisted | `frontend/src/components/KanbanBoard.tsx:76-85` |
| M3 | No cross-session conflict detection (no revision/ETag); concurrent edits from two tabs or devices silently last-write-win | `frontend/src/components/KanbanBoard.tsx` (`persist`), `backend/app/db.py:write_board` |
| M4 | No test coverage for `applyBoardUpdate`, the widest surface for a malformed or adversarial AI response | `frontend/src/lib/kanban.ts:201-279` |

### Low

| # | Finding | Location |
|---|---|---|
| L1 | `requirements.txt` lists `httpx2`, an unused and likely-mistyped dependency | `backend/requirements.txt:5` |
| L2 | Dockerfile uses `pip`, not `uv`, contradicting the documented technical decision; no `pyproject.toml`/`uv.lock` exists | `Dockerfile:13`, `AGENTS.md` |
| L3 | Column-rename fires a full-board `PUT` on every keystroke; no debounce/`onBlur` | `frontend/src/components/KanbanColumn.tsx:44` |
| L4 | No-op `useMemo(() => board.cards, [board.cards])` | `frontend/src/components/KanbanBoard.tsx:113` |
| L5 | `scripts/executionpolicy.ps1` is dead code — not referenced by `start.ps1`/`stop.ps1`, which duplicate its one line inline instead | `scripts/executionpolicy.ps1`, `scripts/stop.ps1:5` |
| L6 | `stop.ps1` sets a persistent, machine-wide `Set-ExecutionPolicy`, unrelated to stopping the app; `start.ps1` doesn't, so behavior is inconsistent | `scripts/stop.ps1:5` |
| L7 | `init_db()` re-runs its full DDL/seed check on every login and registration, not just at startup | `backend/app/db.py:131,151` |
| L8 | `createId()` uses `Math.random()`; `crypto.randomUUID()` is simpler and sufficient | `frontend/src/lib/kanban.ts:164-168` |
| L9 | `package.json`'s `"export": "next export"` script is a leftover pre-`output:"export"`-era command and does nothing useful now | `frontend/package.json:7` |
| L10 | `AIRequest.prompt` has no length limit, unlike the other two user-input models (`Credentials`, `CreateBoard`) | `backend/app/main.py:16-18` |
| L11 | In-memory `sessions` dict is never pruned; grows for the life of the process | `backend/app/main.py:21` |

### Informational

- No structured logging in the backend; auth failures, DB errors, and AI call failures are all silent beyond the HTTP response.
- No `aria-live` region for AI chat responses or the load/save error banner.
- No confirmation dialog before card deletion (`KanbanCard.tsx`'s "Remove" button acts immediately).
- Default `user`/`password` credentials are hardcoded and shown in the login screen copy — a deliberate, documented MVP choice, not an oversight, but a reminder for whenever this stops being purely local.

### Findings from `docs/codereview_oc.md` re-verified as no longer applicable

- **E2E tests bypass authentication (its M4)**: fixed in commit `f07b743`; the current `kanban.spec.ts` logs in via API in `beforeEach` before every navigation. See 5.3.
- **Save queue processes writes out of order (part of its M1)**: not accurate for the current `persist()` implementation, which chains promises and executes strictly in call order. The real, narrower issues (no rollback, no cross-session conflict detection) are captured above as M2/M3.
- **`.dockerignore` missing `frontend/out`/`.next` exclusions (part of its 4.1)**: already present in `.dockerignore`.

---

## 9. Conclusion

The codebase matches its stated goal: a small, honest, local-only Kanban MVP with working auth, multi-board support, drag-and-drop, and AI-assisted editing, none of it over-built. Frontend lint and unit tests pass; backend logic reads correctly against its (unexecutable-here) test suite. The two things worth doing before this grows past a single local user are tightening AI action-update validation on the backend (M1) and giving the frontend a way to tell the user an edit didn't actually save (M2). Everything else — the `uv` migration, script cleanup, debouncing, logging — is incremental polish, not a blocker.
