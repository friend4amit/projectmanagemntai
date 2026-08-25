export type Card = {
  id: string;
  title: string;
  details: string;
};

export type Column = {
  id: string;
  title: string;
  cardIds: string[];
};

export type BoardData = {
  columns: Column[];
  cards: Record<string, Card>;
};

export const initialData: BoardData = {
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
    {
      id: "col-progress",
      title: "In Progress",
      cardIds: ["card-4", "card-5"],
    },
    { id: "col-review", title: "Review", cardIds: ["card-6"] },
    { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
    },
    "card-5": {
      id: "card-5",
      title: "Design card layout",
      details: "Add hierarchy and spacing for scanning dense lists.",
    },
    "card-6": {
      id: "card-6",
      title: "QA micro-interactions",
      details: "Verify hover, focus, and loading states.",
    },
    "card-7": {
      id: "card-7",
      title: "Ship marketing page",
      details: "Final copy approved and asset pack delivered.",
    },
    "card-8": {
      id: "card-8",
      title: "Close onboarding sprint",
      details: "Document release notes and share internally.",
    },
  },
};

const isColumnId = (columns: Column[], id: string) =>
  columns.some((column) => column.id === id);

const findColumnId = (columns: Column[], id: string) => {
  if (isColumnId(columns, id)) {
    return id;
  }
  return columns.find((column) => column.cardIds.includes(id))?.id;
};

export const moveCard = (
  columns: Column[],
  activeId: string,
  overId: string
): Column[] => {
  const activeColumnId = findColumnId(columns, activeId);
  const overColumnId = findColumnId(columns, overId);

  if (!activeColumnId || !overColumnId) {
    return columns;
  }

  const activeColumn = columns.find((column) => column.id === activeColumnId);
  const overColumn = columns.find((column) => column.id === overColumnId);

  if (!activeColumn || !overColumn) {
    return columns;
  }

  const isOverColumn = isColumnId(columns, overId);

  if (activeColumnId === overColumnId) {
    if (isOverColumn) {
      const nextCardIds = activeColumn.cardIds.filter(
        (cardId) => cardId !== activeId
      );
      nextCardIds.push(activeId);
      return columns.map((column) =>
        column.id === activeColumnId
          ? { ...column, cardIds: nextCardIds }
          : column
      );
    }

    const oldIndex = activeColumn.cardIds.indexOf(activeId);
    const newIndex = activeColumn.cardIds.indexOf(overId);

    if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) {
      return columns;
    }

    const nextCardIds = [...activeColumn.cardIds];
    nextCardIds.splice(oldIndex, 1);
    nextCardIds.splice(newIndex, 0, activeId);

    return columns.map((column) =>
      column.id === activeColumnId
        ? { ...column, cardIds: nextCardIds }
        : column
    );
  }

  const activeIndex = activeColumn.cardIds.indexOf(activeId);
  if (activeIndex === -1) {
    return columns;
  }

  const nextActiveCardIds = [...activeColumn.cardIds];
  nextActiveCardIds.splice(activeIndex, 1);

  const nextOverCardIds = [...overColumn.cardIds];
  if (isOverColumn) {
    nextOverCardIds.push(activeId);
  } else {
    const overIndex = overColumn.cardIds.indexOf(overId);
    const insertIndex = overIndex === -1 ? nextOverCardIds.length : overIndex;
    nextOverCardIds.splice(insertIndex, 0, activeId);
  }

  return columns.map((column) => {
    if (column.id === activeColumnId) {
      return { ...column, cardIds: nextActiveCardIds };
    }
    if (column.id === overColumnId) {
      return { ...column, cardIds: nextOverCardIds };
    }
    return column;
  });
};

export const createId = (prefix: string) => {
  const randomPart = Math.random().toString(36).slice(2, 8);
  const timePart = Date.now().toString(36);
  return `${prefix}-${randomPart}${timePart}`;
};

const isValidBoardData = (value: unknown): value is BoardData => {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  if (!Array.isArray(candidate.columns) || typeof candidate.cards !== "object" || candidate.cards === null) {
    return false;
  }

  const cards = candidate.cards as Record<string, unknown>;
  for (const [cardId, card] of Object.entries(cards)) {
    if (!card || typeof card !== "object") return false;
    const { id, title, details } = card as Record<string, unknown>;
    if (id !== cardId || typeof title !== "string" || typeof details !== "string") return false;
  }

  const placedCardIds: string[] = [];
  const columnIds = new Set<string>();
  for (const column of candidate.columns) {
    if (!column || typeof column !== "object") return false;
    const { id, title, cardIds } = column as Record<string, unknown>;
    if (typeof id !== "string" || typeof title !== "string" || !Array.isArray(cardIds)) return false;
    if (columnIds.has(id)) return false;
    columnIds.add(id);
    for (const cardId of cardIds) {
      if (typeof cardId !== "string" || !(cardId in cards) || placedCardIds.includes(cardId)) return false;
      placedCardIds.push(cardId);
    }
  }

  return true;
};

const applyColumnsPatch = (board: BoardData, columns: unknown[]): BoardData | null => {
  const patches = new Map<string, string[]>();
  const claimedCardIds = new Set<string>();

  for (const entry of columns) {
    if (!entry || typeof entry !== "object") return null;
    const { id, cardIds } = entry as Record<string, unknown>;
    if (typeof id !== "string" || !board.columns.some((column) => column.id === id)) return null;
    if (!Array.isArray(cardIds) || patches.has(id)) return null;

    const validatedCardIds: string[] = [];
    for (const cardId of cardIds) {
      if (typeof cardId !== "string" || !(cardId in board.cards) || claimedCardIds.has(cardId)) return null;
      claimedCardIds.add(cardId);
      validatedCardIds.push(cardId);
    }
    patches.set(id, validatedCardIds);
  }

  if (patches.size === 0) return null;

  const nextColumns = board.columns.map((column) => {
    const patch = patches.get(column.id);
    if (patch) return { ...column, cardIds: patch };
    return { ...column, cardIds: column.cardIds.filter((cardId) => !claimedCardIds.has(cardId)) };
  });

  const placedCardIds = nextColumns.flatMap((column) => column.cardIds);
  const allCardIds = Object.keys(board.cards);
  if (placedCardIds.length !== allCardIds.length || new Set(placedCardIds).size !== allCardIds.length) {
    return null;
  }

  return { ...board, columns: nextColumns };
};

export const applyBoardUpdate = (board: BoardData, boardUpdate: unknown): BoardData => {
  if (!boardUpdate || typeof boardUpdate !== "object" || Array.isArray(boardUpdate)) {
    return board;
  }

  const update = boardUpdate as Record<string, unknown>;

  if (Array.isArray(update.columns)) {
    if (typeof update.cards === "object" && update.cards !== null && isValidBoardData(update)) {
      return update;
    }
    return applyColumnsPatch(board, update.columns) ?? board;
  }

  const findColumn = (value: string) => {
    return (
      board.columns.find((column) => column.id === value) ||
      board.columns.find((column) => column.title.toLowerCase() === value.toLowerCase())
    );
  };

  if (update.action === "createCard" && typeof update.card === "object" && update.card !== null) {
    const cardData = update.card as Record<string, unknown>;
    const title = typeof cardData.title === "string" ? cardData.title : "New card";
    const details = typeof cardData.description === "string" ? cardData.description : "No details yet.";
    const columnValue = typeof cardData.column === "string" ? cardData.column : "";
    const targetColumn = findColumn(columnValue) || board.columns[0];
    const id = createId("card");

    return {
      ...board,
      cards: {
        ...board.cards,
        [id]: { id, title, details },
      },
      columns: board.columns.map((column) =>
        column.id === targetColumn.id
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    };
  }

  if (update.action === "renameColumn") {
    const columnId = typeof update.columnId === "string" ? update.columnId : undefined;
    const newTitle = typeof update.title === "string" ? update.title : undefined;
    if (columnId && newTitle) {
      return {
        ...board,
        columns: board.columns.map((column) =>
          column.id === columnId ? { ...column, title: newTitle } : column
        ),
      };
    }
  }

  if (update.action === "moveCard") {
    const cardId = typeof update.cardId === "string" ? update.cardId : undefined;
    const columnValue = typeof update.toColumn === "string" ? update.toColumn : undefined;
    const targetColumn = columnValue ? findColumn(columnValue) : undefined;
    if (cardId && targetColumn) {
      const currentColumn = board.columns.find((column) => column.cardIds.includes(cardId));
      if (!currentColumn || currentColumn.id === targetColumn.id) {
        return board;
      }
      return {
        ...board,
        columns: board.columns.map((column) => {
          if (column.id === currentColumn.id) {
            return { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) };
          }
          if (column.id === targetColumn.id) {
            return { ...column, cardIds: [...column.cardIds, cardId] };
          }
          return column;
        }),
      };
    }
  }

  return board;
};
