import { applyBoardUpdate, moveCard, type BoardData, type Column } from "@/lib/kanban";

describe("moveCard", () => {
  const baseColumns: Column[] = [
    { id: "col-a", title: "A", cardIds: ["card-1", "card-2"] },
    { id: "col-b", title: "B", cardIds: ["card-3"] },
  ];

  it("reorders cards in the same column", () => {
    const result = moveCard(baseColumns, "card-2", "card-1");
    expect(result[0].cardIds).toEqual(["card-2", "card-1"]);
  });

  it("moves cards to another column", () => {
    const result = moveCard(baseColumns, "card-2", "card-3");
    expect(result[0].cardIds).toEqual(["card-1"]);
    expect(result[1].cardIds).toEqual(["card-2", "card-3"]);
  });

  it("drops cards to the end of a column", () => {
    const result = moveCard(baseColumns, "card-1", "col-b");
    expect(result[0].cardIds).toEqual(["card-2"]);
    expect(result[1].cardIds).toEqual(["card-3", "card-1"]);
  });
});

describe("applyBoardUpdate", () => {
  const board: BoardData = {
    columns: [
      { id: "col-backlog", title: "Backlog", cardIds: ["card-1"] },
      { id: "col-review", title: "Review", cardIds: ["card-6"] },
      { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
    ],
    cards: {
      "card-1": { id: "card-1", title: "Test", details: "Test" },
      "card-6": { id: "card-6", title: "QA", details: "QA" },
      "card-7": { id: "card-7", title: "Ship", details: "Ship" },
      "card-8": { id: "card-8", title: "Close", details: "Close" },
    },
  };

  it("applies the moveCard action shape", () => {
    const result = applyBoardUpdate(board, { action: "moveCard", cardId: "card-1", toColumn: "Review" });
    expect(result.columns.find((c) => c.id === "col-backlog")?.cardIds).toEqual([]);
    expect(result.columns.find((c) => c.id === "col-review")?.cardIds).toEqual(["card-6", "card-1"]);
  });

  it("applies a partial columns-only patch without a top-level action field", () => {
    // This is the shape the AI actually returned for "move the Test card to Review":
    // {"columns":[{"id":"col-backlog","cardIds":[]},{"id":"col-review","cardIds":["card-6","card-1"]}]}
    // with no "action" key and no "cards" key.
    const result = applyBoardUpdate(board, {
      columns: [
        { id: "col-backlog", cardIds: [] },
        { id: "col-review", cardIds: ["card-6", "card-1"] },
      ],
    });
    expect(result.columns.find((c) => c.id === "col-backlog")?.cardIds).toEqual([]);
    expect(result.columns.find((c) => c.id === "col-review")?.cardIds).toEqual(["card-6", "card-1"]);
    expect(result.columns.find((c) => c.id === "col-done")?.cardIds).toEqual(["card-7", "card-8"]);
  });

  it("ignores a columns patch that references an unknown card id", () => {
    const result = applyBoardUpdate(board, {
      columns: [{ id: "col-review", cardIds: ["card-6", "card-does-not-exist"] }],
    });
    expect(result).toBe(board);
  });

  it("ignores a columns patch that would duplicate a card across columns", () => {
    const result = applyBoardUpdate(board, {
      columns: [
        { id: "col-backlog", cardIds: ["card-1"] },
        { id: "col-review", cardIds: ["card-6", "card-1"] },
      ],
    });
    expect(result).toBe(board);
  });

  it("applies a valid full board replacement as-is, including title changes", () => {
    const fullBoard: BoardData = {
      columns: [
        { id: "col-backlog", title: "Backlog", cardIds: [] },
        { id: "col-review", title: "Renamed Review", cardIds: ["card-6", "card-1"] },
        { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
      ],
      cards: board.cards,
    };
    const result = applyBoardUpdate(board, fullBoard);
    expect(result).toBe(fullBoard);
    expect(result.columns.find((c) => c.id === "col-review")?.title).toBe("Renamed Review");
  });

  it("falls back to the columns patch when a full board replacement fails validation", () => {
    // "cards" is missing entries the AI's own cardIds reference (fails isValidBoardData),
    // but every referenced card id is still a real card on the existing board, so the
    // columns-patch fallback reorganizes the board against the *existing* card set instead
    // of silently doing nothing.
    const invalidFullBoard = {
      columns: [
        { id: "col-backlog", title: "Backlog", cardIds: [] },
        { id: "col-review", title: "Review", cardIds: ["card-6", "card-1"] },
        { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
      ],
      cards: { "card-1": board.cards["card-1"] },
    };
    const result = applyBoardUpdate(board, invalidFullBoard);
    expect(result).not.toBe(board);
    expect(result.columns.find((c) => c.id === "col-backlog")?.cardIds).toEqual([]);
    expect(result.columns.find((c) => c.id === "col-review")?.cardIds).toEqual(["card-6", "card-1"]);
    expect(result.cards).toBe(board.cards);
  });

  it("no-ops when neither a valid full board nor a valid columns patch can be formed", () => {
    // cardIds reference a card that doesn't exist anywhere.
    const invalidFullBoard = {
      columns: [
        { id: "col-backlog", title: "Backlog", cardIds: [] },
        { id: "col-review", title: "Review", cardIds: ["card-6", "card-1", "card-ghost"] },
        { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
      ],
      cards: board.cards,
    };
    const result = applyBoardUpdate(board, invalidFullBoard);
    expect(result).toBe(board);
  });
});
