# Backend Agent Guidance

## Current state

The `backend/` folder contains a FastAPI app that serves the frontend static output from `backend/app/static`, provides cookie-based local authentication, user-scoped multi-board CRUD endpoints, and integrates with OpenRouter for AI chat.

## Responsibilities

- Build the FastAPI backend that serves the static Next.js build at `/`.
- Add API endpoints for registration, login, logout, current user, user-scoped board retrieval/updates, and AI chat.
- Implement SQLite persistence and migrations for users and multiple named boards.
- Add OpenRouter integration for AI calls using `OPENROUTER_API_KEY` loaded from `.env`.
- Keep the backend minimal, simple, and well-tested.

## Key backend files

- `backend/app/main.py` as the FastAPI entrypoint
- `backend/app/db.py` for SQLite setup and persistence helpers
- `backend/app/schemas.py` for request/response models
- `backend/app/ai.py` for AI integration logic
- `backend/test/test_api.py` and `backend/test/test_ai.py` for backend tests

## Notes

- Boards support rename (`PATCH /api/boards/{id}`) and delete (`DELETE /api/boards/{id}`, 404 if not owned by the caller, 400 if it's the user's only board) in addition to list/create/read/update. See `db.py`'s `rename_board`/`delete_board`.
- `ai.py`'s prompt to the model explicitly documents the exact `boardUpdate` shapes the frontend understands (the `moveCard`/`createCard`/`renameColumn` action objects, or a full `columns`+`cards` replacement) — this matters because the model isn't fine-tuned for this schema and, left unconstrained, would sometimes return a partial `columns`-only diff (no `action`, no `cards`) that `frontend/src/lib/kanban.ts`'s `applyBoardUpdate` couldn't recognize, silently dropping the change while still reporting success in the chat message. See the matching note in `frontend/AGENTS.md`.
- `db.py` opens every connection through the `_connect()` context manager, which guarantees the close; writes still need their own inner `with connection:` block to commit. Every board statement is scoped with `WHERE ... user_id = ?` (or binds `user_id` on INSERT) — that predicate is the ownership boundary, so keep it on any new query.
- `main.py` injects the signed-in user through the `CurrentUser` alias (`Annotated[UserResponse, Depends(get_current_user)]`) rather than repeating `Depends(...)` per route. Route declaration order matters: the `/api/*` routes must stay above the `/` and `/{full_path:path}` SPA fallbacks.
- `ai.py`'s `_parse_response_text` deliberately hunts for the first `{...}` block instead of calling `json.loads` on the whole string. Models wrap their JSON in prose or code fences, so this is required behaviour, not defensive clutter.

## Goals for Part 2 and beyond

- Part 2: scaffolding with a working FastAPI app and a sample API response.
- Part 5: database schema and persistence.
- Part 6: backend routes for board CRUD.
- Part 8-9: AI connectivity and structured response handling.
- Part 10: serve the built frontend and apply AI-generated board updates.
