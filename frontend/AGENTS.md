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
- `frontend/src/lib/kanban.test.ts` - unit tests for `moveCard` and every `applyBoardUpdate` shape.

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

- The current board state loads from the backend and persists through `/api/boards/{id}`. Boards can also be renamed (`PATCH`) and deleted (`DELETE`, rejected with 400 if it's the user's only board) from the board switcher in `KanbanBoard.tsx`.
- The existing UI supports column rename, card add, delete, and drag/drop.
- AI chat updates are handled by applying structured `boardUpdate` action objects to the existing board.
- Board columns render in a horizontal flex strip (`KanbanBoard.tsx`) that lets each column grow to fill available width (`min-w-[280px] flex-1` in `KanbanColumn.tsx`) and falls back to horizontal scroll (`overflow-x-auto`) once columns hit that 280px floor, rather than squeezing into a fixed grid — this keeps columns usable at both narrow and wide viewports. The AI chat sidebar stacks full-width below the board up to a custom `min-[1900px]` breakpoint (chosen so five 280px columns plus the 360px sidebar actually fit side by side without scrolling) and only docks beside the board above that width.
- Card delete is an icon-only button (inline SVG trash icon, no external icon library) with `aria-label`/`title` for accessibility — no visible "Remove" text.
- `applyBoardUpdate` (`lib/kanban.ts`) accepts three `boardUpdate` shapes from the AI: a full `columns`+`cards` replacement, one of the `action` objects (`moveCard`/`createCard`/`renameColumn`), or — as a fallback — a partial `columns` array with no `action`/`cards` (e.g. `{"columns":[{"id":"col-a","cardIds":[...]}]}`). That partial shape is what the model returned for some move phrasings before the backend prompt (`backend/app/ai.py`) was tightened to spell out the exact expected shapes; the fallback is kept as a safety net in case a future model/phrasing still emits it. The fallback (`applyColumnsPatch`) only commits the patch if every referenced card id is known and every original card still ends up in exactly one column afterward; otherwise it's a no-op, same as an unrecognized shape. It also fires when a "full board" update fails strict validation (e.g. its own `cards` map is incomplete) but its `columns`/`cardIds` are still valid against the *existing* board's cards — in that case the reorganization is still applied, just against the current card set rather than whatever the update's `cards` field claimed. See `lib/kanban.test.ts` for the reproduction case and this fallback-commit case.
- JSON requests go through `apiSendJson(path, method, body)` in `lib/api.ts`, which wraps `apiFetch` with the method, `Content-Type` header, and `JSON.stringify`. `apiFetch` is still the right call for bodyless requests (GET, DELETE).
- `applyBoardUpdate` dispatches the `action` shapes to `applyCreateCard`/`applyRenameColumn`/`applyMoveCard`, with the full-replacement and partial-`columns` paths handled before the dispatch. Every unrecognized or incomplete update returns the original `board` object by reference, which several tests in `lib/kanban.test.ts` assert with `toBe`; preserve that when adding a new action.
