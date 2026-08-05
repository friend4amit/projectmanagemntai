# Backend Agent Guidance

## Current state

The `backend/` folder now contains a working FastAPI app. It serves the frontend static output from `backend/app/static`, provides board CRUD endpoints, and integrates with OpenRouter for AI chat.

## Responsibilities

- Build the FastAPI backend that serves the static Next.js build at `/`.
- Add API endpoints for authentication, board retrieval, board updates, and AI chat.
- Implement SQLite persistence, creating the database file if it does not exist.
- Add OpenRouter integration for AI calls using `OPENROUTER_API_KEY` loaded from `.env`.
- Keep the backend minimal, simple, and well-tested.

## Key backend files

- `backend/app/main.py` as the FastAPI entrypoint
- `backend/app/db.py` for SQLite setup and persistence helpers
- `backend/app/schemas.py` for request/response models
- `backend/app/ai.py` for AI integration logic
- `backend/test/test_api.py` for backend tests

## Goals for Part 2 and beyond

- Part 2: scaffolding with a working FastAPI app and a sample API response.
- Part 5: database schema and persistence.
- Part 6: backend routes for board CRUD.
- Part 8-9: AI connectivity and structured response handling.
- Part 10: serve the built frontend and apply AI-generated board updates.
