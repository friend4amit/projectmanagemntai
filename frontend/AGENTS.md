# Frontend Agent Guidance

## Current state

The `frontend/` folder contains a Next.js app with a working Kanban app. The UI is implemented in React with drag-and-drop using `@dnd-kit` and board state is now loaded from and persisted to the backend API.

The frontend supports backend-authenticated local accounts, selecting or creating boards for the signed-in user, and an AI chat sidebar that applies structured `boardUpdate` actions returned by the backend.

## Key files

- `frontend/src/app/page.tsx` - application entry point that restores the authenticated user and renders the `LoginForm` or `KanbanBoard`.
- `frontend/src/components/KanbanBoard.tsx` - the board container, drag/drop handling, and board state.
- `frontend/src/components/KanbanColumn.tsx` - column rendering and card list.
- `frontend/src/components/KanbanCard.tsx` - card display.
- `frontend/src/components/KanbanCardPreview.tsx` - drag overlay preview.
- `frontend/src/components/NewCardForm.tsx` - adding new cards.
- `frontend/src/components/LoginForm.tsx` - login screen and auth state.
- `frontend/src/components/AIChatPanel.tsx` - AI chat sidebar and response handling.
- `frontend/src/lib/kanban.ts` - board model, initial data, card movement helpers, and AI update application.
- `frontend/src/components/KanbanBoard.test.tsx` - component tests for board behavior.

## Responsibilities

- Keep the UI simple and aligned with the MVP goals.
- Convert the demo into a real authenticated app.
- Load, create, select, and save user-scoped board state through the backend API.
- Add AI chat sidebar and structured board update handling.
- Add frontend tests for login, board persistence, and AI chat.

## Goals for the next phases

- Part 3: verify build and connect the frontend to backend static serving.
- Part 4: add login and logout.
- Part 7: consume board API and persist state.
- Part 10: add AI chat UI and board update handling.

## Notes

- The current board state loads from the backend and persists through `/api/board`.
- The existing UI supports column rename, card add, delete, and drag/drop.
- AI chat updates are handled by applying structured `boardUpdate` action objects to the existing board.
