# Code review

Date: 2026-08-25
Scope: full repository (`backend/`, `frontend/`, `scripts/`, root Docker/config files).
Method: source review of every backend/frontend source file, plus live verification against a container built from the current `Dockerfile` (`docker build` + `docker run`) — findings marked **Verified live** were reproduced against the running app, not just inferred from source. This supersedes the root-level `review.md`, which was written against a pre-Part-11 checkout; where a `review.md` finding is still relevant it is re-stated here with current status.

## Outcome

The MVP is compact and mostly does what `docs/PLAN.md` claims. This review found one **critical, exploitable, unauthenticated arbitrary-file-read vulnerability** in the backend's static-file fallback route, compounded by the fact that the live SQLite database (containing user credentials, stored in plaintext) was committed to git. Beyond that, there were previously-known gaps (unvalidated AI board updates, racy saves, stale static build, e2e tests that didn't log in) plus several new lower-severity findings.

**Update (2026-08-25, same day): all Critical, High, and Medium findings below have been fixed and re-verified** — see the "Remediation" line on each finding and the summary table below. One Low item (stray test card in `board.json`) was fixed opportunistically; the rest remain open.

## Remediation summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Path traversal in static fallback route | Critical | **Fixed** — verified live: traversal payloads now 404/fall through to `index.html` |
| 2 | `database.db` committed to git | Critical | **Fixed in working tree** (untracked + gitignored); git *history* still contains it — needs your decision, see below |
| 3 | Plaintext password storage | High | **Fixed** — PBKDF2-HMAC-SHA256 hashing, verified via live login/reject |
| 4 | AI `boardUpdate` accepted with no invariant checks | High | **Fixed** — server-side Pydantic validator + client-side type guard, verified live (422 on a malformed board) |
| 5 | Unserialized racy board saves | Medium | **Fixed** — writes now queued per-board |
| 6 | Stale committed static build | Medium | **Fixed** — `backend/app/static` untracked + gitignored; Docker always regenerates it fresh |
| 7 | E2E tests don't authenticate | Medium | **Fixed** — tests now log in first; re-run: 5/5 pass (2 new tests added) |
| 8 | `frontend/README.md` dev quickstart broken | Medium | **Fixed** — dev-mode API base + scoped CORS so `npm run dev` works against a locally-running backend |
| 9 | Stray test card in `board.json` | Low | Fixed opportunistically |
| 10–13 | `pip` vs `uv`, PowerShell execution-policy side effect, no CI, hand-rolled `.env` parsing | Low | Still open (unchanged from original findings below) |

## Action items (priority order) — original list, kept for record

1. ~~Fix the path-traversal in `backend/app/main.py`'s static fallback route~~ — **Fixed**. (Critical)
2. ~~Stop committing `backend/app/database.db` to git~~ — **Fixed going forward; history not rewritten, pending your decision.** (Critical)
3. ~~Hash passwords~~ — **Fixed.** (High)
4. ~~Validate `boardUpdate` server-side~~ — **Fixed.** (High)
5. ~~Serialize/await board saves~~ — **Fixed.** (Medium)
6. ~~Rebuild/regenerate `backend/app/static`, or stop versioning it~~ — **Fixed (stopped versioning it).** (Medium)
7. ~~Fix `frontend/tests/kanban.spec.ts` to authenticate~~ — **Fixed.** (Medium)
8. ~~Add a dev-time proxy so `npm run dev` alone works~~ — **Fixed.** (Medium)
9. ~~Remove the stray test card from `backend/app/board.json`~~ — **Fixed.** (Low)
10. Reconcile `Dockerfile`'s `pip` install with the `uv` decision in `AGENTS.md`, or update the doc. (Low — open)
11. Drop the `Set-ExecutionPolicy -Scope CurrentUser` side effect from `scripts/start.ps1`/`stop.ps1`; delete the unused `scripts/executionpolicy.ps1`. (Low — open)
12. Consider adding CI (lint + unit tests on push) so regressions don't silently return. (Low — open)

---

## Findings

### Critical — Unauthenticated arbitrary file read via the static-file fallback route

**Location:** `backend/app/main.py:128-135`

```python
@app.get("/{full_path:path}", response_class=FileResponse)
def read_static(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    candidate = static_dir / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(static_dir / "index.html")
```

`static_dir / full_path` is never resolved or checked for containment inside `static_dir` before being stat'd and served. `full_path` comes directly from the URL, so a `..`-containing (or percent-encoded `..`) path escapes `static_dir` and reads any file readable by the container process — no login required, since this route (unlike `/api/*`) has no auth dependency.

**Verified live** against a container built from the current `Dockerfile`:

```
$ curl "http://localhost:8000/..%2fmain.py"          # -> full contents of backend/app/main.py
$ curl "http://localhost:8000/..%2f..%2f..%2f..%2fetc%2fpasswd"  # -> /etc/passwd
$ curl "http://localhost:8000/..%2fdatabase.db"       # -> a valid, downloadable copy of the live SQLite database
```

All three returned HTTP 200 with the real file contents, with zero authentication. The third is especially bad in combination with the plaintext-password finding below: any unauthenticated visitor can download the entire users table.

**Recommended fix:** resolve the candidate path and verify it's still inside `static_dir` before serving, e.g.:

```python
candidate = (static_dir / full_path).resolve()
if candidate.is_relative_to(static_dir) and candidate.is_file():
    return FileResponse(candidate)
return FileResponse(static_dir / "index.html")
```

(`Path.is_relative_to` requires Python 3.9+; this project targets 3.12, so it's available.) Add a regression test that requests something like `/../main.py` or `/..%2fdatabase.db` and asserts 404/index fallback, not the real file.

**Remediation (2026-08-25):** Fixed exactly as recommended (`backend/app/main.py`'s `read_static` now resolves the candidate and checks `is_relative_to(static_dir)`). Re-ran the same three exploit requests against a fresh `docker build` — all now return the `index.html` fallback instead of the real file contents; a legitimate static asset (`/favicon.ico`) still serves correctly. Added `backend/test/test_api.py::test_static_fallback_rejects_path_traversal` as a permanent regression test (asserts a `/..%2fmain.py` request returns the SPA fallback, not backend source) — passes as part of the full suite (6/6).

### Critical — Live SQLite database (with credentials) is committed to git

**Location:** `backend/app/database.db` (tracked since the `Initial commit`, currently 16KB)

The runtime database file is checked into version control, not gitignored. It currently contains at least the seeded `user`/`password` account and whatever test data has accumulated locally (see the stray test card finding below, which shows the working tree's `board.json` has been hand-edited during dev and committed too). Combined with the plaintext-password finding, any real password a developer registers with locally is one `git add`/`git commit` away from being permanently recorded in history — and, per the path-traversal finding above, is also currently downloadable by anyone who can reach the running server.

**Note:** `.dockerignore` already excludes `*.db` from the Docker *build context*, and `.env` is correctly excluded from git — this is specifically about the file being tracked in the git repo itself, which is a separate concern from the Docker image.

**Recommended fix:** `git rm --cached backend/app/database.db`, add `backend/app/database.db` (or `backend/app/*.db`) to `.gitignore`, and — since this file is small and the repo has few commits — consider scrubbing it from git history (`git filter-repo` or equivalent) given it currently contains a real (if default) password.

**Remediation (2026-08-25):** `git rm --cached` applied, `backend/app/*.db` added to `.gitignore`, and the working-tree copy deleted (regenerates automatically on backend startup, now seeded with a hashed password per the fix below). **Not done:** this repo has a real GitHub remote (`origin`) that has already received pushed commits including the original `Initial commit` containing this file, so the old blob is already in shared history. Rewriting history (`git filter-repo`, then a force-push) is a destructive, hard-to-reverse operation affecting a shared remote — I did not do this without your explicit go-ahead. See the note at the end of this document.

### High — Passwords are stored and compared in plaintext

**Location:** `backend/app/db.py` — `create_user` (`INSERT INTO users (username, password) VALUES (?, ?)`), `authenticate_user` (`WHERE username = ? AND password = ?`); `backend/app/schemas.py`'s `Credentials` has no hashing step anywhere in the request path.

This was tolerable while the only account was the hardcoded `user`/`password` MVP login. Since Part 11 added self-service registration (`POST /api/auth/register`), real users can now pick their own password, which is persisted in cleartext in a SQLite file that (see above) is both committed to git and readable over HTTP without auth. The username/password equality check in SQL is also not constant-time, though that's a minor concern next to storing plaintext at all.

**Recommended fix:** hash on registration (`passlib[bcrypt]` or Python's `hashlib` + a proper KDF like `pbkdf2_hmac`/argon2), store the hash, and verify with a constant-time compare against the hash on login. This is a schema-affecting change (existing rows would need a migration or a one-time reset given this is pre-production).

**Remediation (2026-08-25):** Implemented with stdlib `hashlib.pbkdf2_hmac("sha256", ...)`, a random 16-byte salt per user, 600,000 iterations, and `hmac.compare_digest` for constant-time verification (`backend/app/db.py`: `hash_password`/`verify_password`). No new dependency needed. Since this is pre-production, existing rows weren't migrated — the local database was simply deleted and regenerates fresh (seeded default `user` now stores a proper hash). Verified live: correct password logs in (200), wrong password is rejected (401), and the full backend test suite still passes (6/6, includes `test_default_user_can_log_in_and_has_a_board`).

### High — AI `boardUpdate` payloads are trusted without invariant validation

**Location:** `backend/app/schemas.py:42-44` (`AIResponse.boardUpdate: BoardData | dict[str, Any] | None`), `frontend/src/lib/kanban.ts:170-183` (`applyBoardUpdate`)

```typescript
if (
  Array.isArray(update.columns) &&
  typeof update.cards === "object" &&
  update.cards !== null
) {
  return update as BoardData;   // no invariant checks at all
}
```

Any object shaped like `{columns: [...], cards: {...}}` — whether from the AI model, a flaky OpenRouter response, or a direct caller hitting `PUT /api/boards/{id}` — is accepted as-is. Nothing checks that column/card ids are unique, that every `cardIds` entry has a matching entry in `cards`, or that a card's `id` matches its map key. A malformed board can then make `board.cards[cardId]` resolve to `undefined` when rendering (`frontend/src/components/KanbanBoard.tsx:157`: `cards={column.cardIds.map((cardId) => board.cards[cardId])}`), which will throw inside `KanbanCard`/`KanbanCardPreview` when they read `card.title`.

**Recommended fix:** validate board invariants server-side (ideally with a dedicated Pydantic validator on `BoardData`, or an explicit action-based schema for AI updates instead of allowing raw full-board replacement) before persisting or returning a `boardUpdate`, and defensively filter/guard `undefined` cards on the frontend render path regardless.

**Remediation (2026-08-25):** Added a Pydantic `model_validator` on `BoardData` (`backend/app/schemas.py`) checking unique column ids, that every `cards` dict key matches its card's `id`, that no card is placed in more than one column, and that every `cardIds` entry references a real card — this applies automatically to `PUT /api/boards/{id}` regardless of who's calling it (AI-applied update, direct API caller, etc.). Added a matching `isValidBoardData` type guard in `frontend/src/lib/kanban.ts`'s `applyBoardUpdate`, so a malformed full-board AI response is rejected client-side before it's ever rendered (rather than only being caught after an async `PUT` round-trip). Also added a cheap `.filter(Boolean)` in `KanbanBoard.tsx`'s card-rendering as defense-in-depth. Verified live: `PUT /api/boards/{id}` with a board referencing a nonexistent card now returns `422` with a descriptive error instead of `200`.

### Medium — Concurrent board saves aren't serialized (still open, was flagged before)

**Location:** `frontend/src/components/KanbanBoard.tsx:74-81`

```typescript
const persist = (nextBoard: BoardData) => {
  if (boardId === null) return;
  setBoard(nextBoard);
  void syncBoard(boardId, nextBoard).catch((error) => { ... });
};
```

Every drag/rename/add/delete calls `persist()`, which fires an unawaited `PUT` with no queueing or revision check. Two rapid edits can complete out of order, letting an older full-board write silently overwrite a newer one. This is improved since the last review in that `syncBoard` now does check `response.ok` and surfaces a `loadError` — but the underlying race is unchanged.

**Recommended fix:** serialize writes (e.g. a simple in-flight promise chain / mutex keyed by `boardId`), or attach a revision/`updated_at` value the backend can use to reject stale writes with a 409.

**Remediation (2026-08-25):** Implemented the in-flight promise-chain approach — `persist()` now appends each save onto a `useRef`-held promise chain (`saveQueue`), so writes for a given board always reach the backend in the order they were made, and a save failure doesn't break the chain for subsequent saves. Verified via the full frontend unit suite (7/7) and e2e suite (5/5) still passing with drag/rename/add/delete flows exercised.

### Medium — Checked-in static build is stale relative to `frontend/src` (still open)

**Location:** `backend/app/static/index.html` (dated 2026-08-05 12:02) vs. `frontend/src/{page.tsx, AIChatPanel.tsx, KanbanBoard.tsx, LoginForm.tsx}` (all modified later the same day, per filesystem mtimes)

Running the backend directly against this checkout (outside a fresh `docker build`) serves an outdated UI that predates the AI chat panel and current login flow. `Dockerfile` regenerates this correctly on every build, but the *committed* copy in the repo drifts out of sync with source whenever frontend changes land without a corresponding rebuild+commit of `backend/app/static`.

**Recommended fix:** either stop versioning `backend/app/static` (build-only artifact, gitignore it) or add a pre-commit/CI check that fails if source changed more recently than the built output.

**Remediation (2026-08-25):** Chose to stop versioning it — `git rm --cached -r backend/app/static` and added `backend/app/static/` to `.gitignore`. `Dockerfile` already regenerates this fresh on every build (unchanged), so this eliminates the staleness class of bug entirely rather than just refreshing the snapshot once more.

### Medium — E2E tests don't authenticate, so they fail against the real app (still open, now verified live)

**Location:** `frontend/tests/kanban.spec.ts`

**Verified live**: ran `npx playwright test` against the actual running container (not just `next dev`). All 3 tests fail — `page.goto("/")` renders `LoginForm` (since there's no session cookie), so `getByRole("heading", { name: "Kanban Studio" })` and the column/card test-ids the other two tests depend on never appear.

**Recommended fix:** add a login step (via UI or by seeding a session cookie through the API) in a `beforeEach`/fixture, then add explicit positive/negative login-logout tests as `docs/PLAN.md`'s Part 4 success criteria originally called for.

**Remediation (2026-08-25):** Added a `test.beforeEach` that logs in via `page.request.post` against the backend directly (fast, shares the cookie jar with `page`), wrapping the original 3 tests in an `authenticated board` describe block. Added two new tests: a logout test and an invalid-credentials test (unauthenticated, outside the describe block). Re-ran against the real app (Docker container on :8000 + `next dev` on :3000, per the fix below) — **5/5 pass**.

### Medium — `frontend/README.md`'s documented dev workflow doesn't actually work standalone

**Location:** `frontend/README.md` (`npm install && npm run dev`), `frontend/src/components/{LoginForm,KanbanBoard,AIChatPanel}.tsx` (all call relative paths like `fetch("/api/auth/me")`), no CORS middleware in `backend/app/main.py`, no rewrites/proxy in `frontend/next.config.ts`

The frontend's own README says to run `npm install && npm run dev` to develop it, but every API call in the app is a same-origin relative fetch. `next dev` alone serves nothing at `/api/*`, so following the README literally gives a UI stuck on "Loading..." / a broken login screen. The only way the frontend actually functions today is served from the backend (i.e., built into `backend/app/static` and run via Docker) — which also makes iterating on frontend code slow (full Docker rebuild per change).

**Recommended fix:** add a dev proxy (Next.js `rewrites()` in `next.config.ts` pointing `/api/*` at `http://localhost:8000`) so `npm run dev` + a locally-running backend actually works together, and update the README to mention the backend must also be running.

**Remediation (2026-08-25):** Used a different mechanism than originally suggested — `next.config.ts` has `output: "export"`, and Next's static-export mode does not support `rewrites()`/`redirects()`/`headers()`, so adding one there risked breaking the production build (the same one `Dockerfile` relies on). Instead added `frontend/src/lib/api.ts` (`apiFetch`), which prefixes API calls with `http://localhost:8000` only when `NODE_ENV === "development"` (empty/same-origin in `test` and `production`, so existing unit tests and the production build are unaffected) and always sends `credentials: "include"`. Replaced every `fetch("/api/...")` call site with `apiFetch(...)` across `page.tsx`, `LoginForm.tsx`, `KanbanBoard.tsx`, `AIChatPanel.tsx`. Added scoped `CORSMiddleware` in `backend/app/main.py` allowing only `http://localhost:3000`/`http://127.0.0.1:3000` with credentials — inert in production since the browser only sends `Origin` for cross-origin requests, which never happens when everything is served from one origin. Updated `frontend/README.md`. Verified live via the e2e suite (`next dev` on :3000 talking to the Docker-run backend on :8000, real login/board/logout flows) — 5/5 pass.

### Low — Committed default board seed contains leftover test data

**Location:** `backend/app/board.json` — the `col-discovery` column's `cardIds` includes `"card-skapnqmsfq5dsq"`, and `cards` includes a matching entry `{"title": "test", "details": "test"}`.

This file is the seed used for every newly registered user's default board and every new board created via `POST /api/boards` (`backend/app/db.py::_load_default_board`). A manual test edit was committed here, so every new board in the product will start with a stray "test" card in the Discovery column.

**Recommended fix:** remove the `card-skapnqmsfq5dsq` entry from both `columns` and `cards` in `board.json`.

**Remediation (2026-08-25):** Removed.

### Low — `Dockerfile` doesn't follow the `uv` decision recorded in `AGENTS.md` (still open, restated from `review.md`)

**Location:** `Dockerfile:13` (`RUN pip install --no-cache-dir -r requirements.txt`) vs. `AGENTS.md`'s "Use `uv` as the package manager for python in the Docker container"

No `pyproject.toml`/lockfile exists; `requirements.txt` uses open-ended lower bounds (`fastapi>=0.121.0`, etc.), so builds aren't pinned/reproducible. Either adopt `uv` as documented, or update `AGENTS.md` to reflect the actual `pip`-based approach.

### Low — PowerShell scripts mutate a persistent user setting as a side effect (still open, restated from `review.md`)

**Location:** `scripts/start.ps1:6`, `scripts/stop.ps1:5` — both run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

Starting or stopping the app shouldn't change the developer's persistent PowerShell execution policy, and this can be blocked by org policy anyway (making the scripts fail outright in a locked-down environment for an unrelated reason). There is also a third, unused file — `scripts/executionpolicy.ps1` — that duplicates this same line but isn't invoked from anywhere (`start.ps1`/`stop.ps1` inline the command rather than calling this script).

**Recommended fix:** remove the `Set-ExecutionPolicy` calls from `start.ps1`/`stop.ps1` (document `powershell -ExecutionPolicy Bypass -File ...` as the workaround for restricted policies instead), and delete the orphaned `scripts/executionpolicy.ps1`.

### Low — No CI configured

**Location:** repo root (no `.github/workflows/`)

Nothing runs `npm run lint`, `npm run test:unit`, or `pytest` automatically on push/PR. This is how issues like the earlier lint failure (now fixed, per `docs/PLAN.md`) or the stale static build (still open, above) go unnoticed until a manual review catches them.

**Recommended fix:** add a basic workflow running frontend lint + unit tests and backend pytest on every push.

### Low — `.env` parsing is hand-rolled and slightly fragile

**Location:** `backend/app/ai.py:13-22` (`_load_dotenv_if_present`)

```python
for line in env_path.read_text(encoding="utf-8").splitlines():
    if not line or line.strip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
```

Works for the project's current single-line `.env`, but doesn't handle quoted values, inline comments after a value, or `export KEY=value` syntax the way a real `.env` parser (e.g. `python-dotenv`) would. Low priority given the current `.env` is trivial, but worth switching to a real parser if `.env` usage grows.

## Verification performed

### Initial review pass

- `docker build` from the current `Dockerfile`, then `docker run` — used as the substrate for all "Verified live" findings above (path traversal, e2e-against-real-backend).
- `backend/test/test_api.py` executed inside the built container (`python -m pytest`, 5/5 passed) — confirms the currently-known auth/ownership/board tests still pass; none of them cover the path-traversal route or password hashing, which is why those gaps weren't previously caught.
- `frontend`: `npm run test:unit` (7/7 passed), `npm run lint` (passes, 0 exit code), `npx playwright test` against the live container (3/3 failed — see finding above).
- `git ls-files` / `git log` used to confirm `backend/app/database.db` is tracked and check `.gitignore` coverage.
- File mtimes compared (`find -newer`) to confirm the static-build staleness claim.

### Remediation pass (2026-08-25, same day)

- Fresh `docker build` after all fixes — succeeded, including `next build`'s TypeScript check over the changed frontend files.
- `backend/test/test_api.py` run inside the rebuilt container: **6/6 passed** (5 original + the new path-traversal regression test).
- Path-traversal exploit requests (`/..%2fmain.py`, `/..%2f.../etc/passwd`, `/..%2fdatabase.db`) re-run against the fixed container — all now return the SPA fallback, not real file contents. Legitimate static asset (`/favicon.ico`) still serves correctly.
- Login/auth flow re-verified via curl: correct password → `200`; wrong password → `401`; session cookie grants `/api/boards` access.
- Board invariant validator re-verified via curl: a `PUT` with a `cardIds` entry referencing a nonexistent card → `422` with a descriptive error (previously `200`).
- `frontend`: `npm run test:unit` (7/7 passed), `npm run lint` (0 exit code) — confirms the `NODE_ENV === "development"`-gated `apiFetch` change doesn't affect the `test` or `production` code paths.
- `npx playwright test` run against the real stack (Docker container serving the backend on `:8000` + `next dev` on `:3000`, exercising the new dev-mode CORS/API-base fix) — **5/5 passed** (3 original tests, now authenticated, + 2 new: logout, invalid-credentials).
- All test/verification Docker containers stopped and removed after each check; no stray processes left listening.

## Outstanding — needs your decision

**Git history still contains `backend/app/database.db`** from the original `Initial commit`, and this repository has a real GitHub remote (`origin` → `github.com/friend4amit/projectmanagemntai`) with commits already pushed. The working tree is now fixed (file untracked, gitignored, regenerates locally), but the *history* still has the old blob — meaning the seeded `user`/`password` credential (now superseded by hashing, but still a real value that was live) is still recoverable by anyone who can read the repo. Scrubbing it (`git filter-repo` + a force-push to `origin`) is a destructive, hard-to-reverse operation affecting shared remote history, so it wasn't done as part of this pass without your explicit go-ahead. Let me know if you'd like that done.

**None of these fixes have been committed** — everything above is in the working tree only, per the standing rule to only commit when asked. Let me know if you'd like these committed (and whether as one commit or split by concern).

## Out of scope / not verified

- No load, fuzz, or dependency-vulnerability (e.g. `pip-audit`/`npm audit`) scanning was performed.
- OpenRouter API behavior itself (the third-party model's actual output shape/quality) was not exercised — `OPENROUTER_API_KEY` in `.env` was present but no live AI chat request was sent as part of this review.
- Windows-specific script behavior (`start.ps1`/`stop.ps1`) was read but not executed, since running them would rebuild/restart the app outside this review's container-based verification flow.
- The remaining open Low findings (10–12: `pip` vs `uv`, PowerShell execution-policy side effect, no CI) were left as-is — out of scope for this remediation pass, which focused on Critical/High/Medium per your request.
