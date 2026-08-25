"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors, closestCorners, type DragEndEvent, type DragStartEvent } from "@dnd-kit/core";
import { AIChatPanel } from "@/components/AIChatPanel";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import type { AuthenticatedUser } from "@/components/LoginForm";
import { createId, initialData, moveCard, type BoardData } from "@/lib/kanban";

type BoardSummary = { id: number; title: string };

type KanbanBoardProps = {
  user: AuthenticatedUser;
  onLogout: () => void;
};

const syncBoard = async (boardId: number, nextBoard: BoardData) => {
  const response = await fetch(`/api/boards/${boardId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(nextBoard),
  });
  if (!response.ok) {
    throw new Error(`Board save failed: ${response.status}`);
  }
};

export const KanbanBoard = ({ user, onLogout }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData>(initialData);
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [boardId, setBoardId] = useState<number | null>(null);
  const [newBoardTitle, setNewBoardTitle] = useState("");
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const loadBoards = async () => {
      try {
        const response = await fetch("/api/boards");
        if (!response.ok) throw new Error(`Board list failed: ${response.status}`);
        const data: BoardSummary[] = await response.json();
        setBoards(data);
        setBoardId(data[0]?.id ?? null);
      } catch (error) {
        setLoadError("Unable to load your boards.");
        setIsLoading(false);
        console.error(error);
      }
    };
    void loadBoards();
  }, []);

  useEffect(() => {
    if (boardId === null) return;
    const loadBoard = async () => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const response = await fetch(`/api/boards/${boardId}`);
        if (!response.ok) throw new Error(`Board load failed: ${response.status}`);
        setBoard(await response.json());
      } catch (error) {
        setLoadError("Unable to load this board.");
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };
    void loadBoard();
  }, [boardId]);

  const persist = (nextBoard: BoardData) => {
    if (boardId === null) return;
    setBoard(nextBoard);
    void syncBoard(boardId, nextBoard).catch((error) => {
      setLoadError("Unable to save this board. Refresh and try again.");
      console.error(error);
    });
  };

  const handleLogout = async () => {
    await fetch("/api/logout", { method: "POST" });
    onLogout();
  };

  const handleCreateBoard = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newBoardTitle.trim()) return;
    try {
      const response = await fetch("/api/boards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newBoardTitle.trim() }),
      });
      if (!response.ok) throw new Error(`Board creation failed: ${response.status}`);
      const created: BoardSummary = await response.json();
      setBoards((current) => [created, ...current]);
      setNewBoardTitle("");
      setBoardId(created.id);
    } catch (error) {
      setLoadError("Unable to create a board.");
      console.error(error);
    }
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const cardsById = useMemo(() => board.cards, [board.cards]);

  const handleDragStart = (event: DragStartEvent) => setActiveCardId(event.active.id as string);
  const handleDragEnd = (event: DragEndEvent) => {
    setActiveCardId(null);
    if (!event.over || event.active.id === event.over.id) return;
    persist({ ...board, columns: moveCard(board.columns, event.active.id as string, event.over.id as string) });
  };
  const handleRenameColumn = (columnId: string, title: string) => persist({ ...board, columns: board.columns.map((column) => column.id === columnId ? { ...column, title } : column) });
  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    persist({ ...board, cards: { ...board.cards, [id]: { id, title, details: details || "No details yet." } }, columns: board.columns.map((column) => column.id === columnId ? { ...column, cardIds: [...column.cardIds, id] } : column) });
  };
  const handleDeleteCard = (columnId: string, cardId: string) => persist({ ...board, cards: Object.fromEntries(Object.entries(board.cards).filter(([id]) => id !== cardId)), columns: board.columns.map((column) => column.id === columnId ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) } : column) });

  if (isLoading) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-700">Loading board...</div>;
  if (boardId === null) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-700">No boards available.</div>;

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      {loadError ? <div className="fixed left-4 top-4 rounded-2xl bg-amber-100 px-4 py-3 text-sm text-amber-950 shadow-[var(--shadow)]">{loadError}</div> : null}
      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">{user.username}&apos;s workspace</p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">Kanban Studio</h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">Choose a board, create another project space, and keep momentum visible.</p>
            </div>
            <button type="button" onClick={handleLogout} className="rounded-2xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-900 shadow-sm hover:bg-slate-50">Sign out</button>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-56 flex-1 flex-col gap-2 text-sm font-semibold text-[var(--navy-dark)]">Current board
              <select value={boardId} onChange={(event) => setBoardId(Number(event.target.value))} className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 font-normal">
                {boards.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
            </label>
            <form onSubmit={handleCreateBoard} className="flex flex-1 gap-2">
              <input value={newBoardTitle} onChange={(event) => setNewBoardTitle(event.target.value)} placeholder="New board name" className="min-w-40 flex-1 rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm" />
              <button type="submit" className="rounded-xl bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white">Create board</button>
            </form>
          </div>
        </header>
        <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="grid gap-6 xl:grid-cols-[1.6fr_0.9fr]">
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => <KanbanColumn key={column.id} column={column} cards={column.cardIds.map((cardId) => board.cards[cardId])} onRename={handleRenameColumn} onAddCard={handleAddCard} onDeleteCard={handleDeleteCard} />)}
            </section>
            <AIChatPanel board={board} boardId={boardId} onBoardUpdate={persist} />
          </div>
          <DragOverlay>{activeCard ? <div className="w-[260px]"><KanbanCardPreview card={activeCard} /></div> : null}</DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
