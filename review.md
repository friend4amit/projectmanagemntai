# Code review

## Outcome

The MVP has a clear, compact structure and the frontend unit suite passes, but I would not treat it as ready to hand off yet. The main concerns are that authentication is only cosmetic, board writes can be lost, and the checked-in static frontend is out of date. The project also currently fails its lint check.

## Findings

### High — Backend board and AI endpoints are not authenticated

`frontend/src/components/LoginForm.tsx:18` accepts the hardcoded credentials only in the browser and stores an easily forgeable `localStorage` flag. The backend has no login route or authentication dependency: `backend/app/main.py:35`, `:40`, `:48`, and `:60` expose logout, AI chat, board reads, and board writes without checking a user or session. `logout` only returns a success message.

Any local process can therefore call `GET` or `PUT /api/board`, or use the AI endpoint, without signing in; it can also overwrite the single persisted board. This does not meet the stated requirement that a user must sign in before seeing and changing their board, and it leaves the `users` table unused for authorization.

Recommended fix: implement a minimal backend login/session mechanism for the hardcoded user and require it on board and AI routes. Associate board reads/writes with the authenticated user rather than the constant user id.

### High — AI board updates are trusted without enforcing board invariants

`backend/app/schemas.py:24` permits `boardUpdate` to be an arbitrary dictionary. In `frontend/src/lib/kanban.ts:177-183`, an object with `columns` and `cards` is blindly cast to `BoardData` and installed as UI state. The backend `BoardData` model validates basic field types only; it does not ensure unique column/card ids, that every `cardIds` value exists, that cards occur exactly once, or that a card object's `id` matches its map key.

An imperfect AI response (or a direct API caller) can persist an inconsistent board. The next render can then pass `undefined` cards to `KanbanCard` (`frontend/src/components/KanbanBoard.tsx:154`), causing a client-side failure or silent data loss.

Recommended fix: use a discriminated action schema for AI operations and validate all actions server-side. If full-board replacement is retained, validate the complete board invariants before returning or persisting it.

### Medium — Concurrent saves can overwrite newer board edits

Each handler calls `void syncBoard(nextBoard)` without awaiting or serializing it (`frontend/src/components/KanbanBoard.tsx:79, 91, 110, 125, 130`). `syncBoard` sends the whole board and does not check the response status (`:22-33`). Two rapid edits can complete out of order: an older full-board `PUT` may arrive last and erase the newer change. A rejected `PUT` likewise leaves the UI looking successful until reload.

Recommended fix: serialize saves (or attach a revision and reject stale writes), check `response.ok`, and surface/save-retry failures to the user.

### Medium — The checked-in static site does not match the frontend source

The backend serves `backend/app/static` directly (`backend/app/main.py:25, 65-74`). Its `index.html` was generated at 12:02 on 5 August, while `frontend/src/components/AIChatPanel.tsx` was modified at 15:22 the same day, and the static output contains none of the AI-panel strings. Running the backend from the current checkout therefore serves an older UI that omits the implemented AI feature.

The Dockerfile should regenerate the assets during a successful build, but the repository's runtime artifact is stale. Rebuild and commit the static output when it is intentionally versioned, or do not version it and make the build/deployment path the sole source of generated assets.

### Medium — End-to-end tests do not perform the required login

Every Playwright test goes directly to `/` and expects the Kanban heading (`frontend/tests/kanban.spec.ts:3-6`). A new browser context is unauthenticated, so the application correctly shows `LoginForm` instead. These tests will fail after browser installation even if the app works, and they do not verify login/logout.

Recommended fix: log in in test setup (or seed storage deliberately), then add separate positive and negative login/logout tests.

### Low — The required frontend lint check currently fails

`npm run lint` fails on `frontend/src/app/page.tsx:11`: React's lint rule rejects the synchronous `setIsAuthenticated` call inside `useEffect`. The production check is therefore red despite the six Vitest tests passing.

Recommended fix: initialize authentication in a lint-compliant way (for example, defer the client-only read through an external-store pattern or an explicitly client-only initialization design) and keep lint as a passing gate.

### Low — Docker does not follow the project's stated `uv` requirement

The project plan requires `uv` in the container, but `Dockerfile:13` installs Python packages with `pip` and no `uv` project metadata or lockfile exists. This is a documented technical-decision mismatch and reduces build reproducibility because backend requirements are broad lower bounds.

Recommended fix: add `pyproject.toml` and a lockfile, then install with `uv` in the runtime image as specified.

### Low — PowerShell scripts change a persistent user policy

`scripts/start.ps1:6` and `scripts/stop.ps1:5` run `Set-ExecutionPolicy -Scope CurrentUser`. Starting or stopping this app should not alter a developer's persistent PowerShell configuration, and the command can be blocked by organizational policy.

Recommended fix: remove these lines and document that callers may use `powershell -ExecutionPolicy Bypass -File ...` if their local policy requires it.

## Verification performed

- `npm run test` in `frontend/`: passed (6 tests).
- `npm run lint` in `frontend/`: failed with the `set-state-in-effect` error described above.
- `npm run test:e2e` in `frontend/`: could not launch because the Playwright Chromium executable is not installed. Independently, source inspection confirms the tests bypass login.
- Backend pytest was not run because this workspace has no available Python or `uv` executable.
- Container build was not completed because the required elevated Docker permission was declined.

## Review scope

This was a source and test review of the current checkout against `docs/PLAN.md`. Existing user changes in `scripts/start.ps1` and `scripts/stop.ps1` were not modified.
