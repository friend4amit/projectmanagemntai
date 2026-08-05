# The Project Management MVP web app

## Project goal

Build a local MVP that combines a Next.js Kanban frontend, a Python FastAPI backend, SQLite persistence, and an AI chat assistant that can update the board.

## Current implementation status

- Frontend and backend are integrated and deployed in Docker.
- Authentication is implemented with local auth state and logout.
- Board state is persisted in SQLite via backend API routes.
- AI chat now returns structured `boardUpdate` actions and the frontend applies them to the board.
- `OPENROUTER_API_KEY` is loaded from `.env` and passed into Docker with `--env-file .env`.

## Business requirements

- A user can sign in.
- When signed in, the user sees a single Kanban board representing their project.
- The Kanban board has fixed columns that can be renamed.
- Cards can be moved, added, and deleted.
- An AI chat sidebar can create, edit, move, or update cards.

## Limitations

- One hardcoded user: `user` / `password`.
- One board per user.
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

## Coding standards

- Use modern idiomatic code.
- Keep the implementation simple.
- Avoid unnecessary complexity.
- Fix root causes, not symptoms.

## Working documentation

All planning and execution documentation is in `docs/`.
Agent docs and the plan must be kept current before making code changes.
