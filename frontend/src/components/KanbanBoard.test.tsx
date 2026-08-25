import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const user = { id: 1, username: "user" };
const boards = [{ id: 1, title: "My first board" }];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.url;
      if (url === "/api/boards" && init?.method === "POST") {
        return { ok: true, json: async () => ({ id: 2, title: "Second board" }) };
      }
      if (url === "/api/boards") {
        return { ok: true, json: async () => boards };
      }
      return { ok: true, json: async () => initialData };
    }));
  });

  const renderBoard = () => render(<KanbanBoard user={user} onLogout={() => {}} />);

  it("renders five columns", async () => {
    renderBoard();
    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    renderBoard();
    const column = (await screen.findAllByTestId(/column-/i))[0];
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    await waitFor(() => expect(input).toHaveValue("New Name"));
  });

  it("adds and removes a card", async () => {
    renderBoard();
    const column = (await screen.findAllByTestId(/column-/i))[0];
    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));
    await waitFor(() => expect(within(column).getByText("New card")).toBeInTheDocument());
    await userEvent.click(within(column).getByRole("button", { name: /delete new card/i }));
    await waitFor(() => expect(within(column).queryByText("New card")).not.toBeInTheDocument());
  });

  it("creates and selects a new board", async () => {
    renderBoard();
    await screen.findByRole("combobox", { name: /current board/i });
    await userEvent.type(screen.getByPlaceholderText("New board name"), "Second board");
    await userEvent.click(screen.getByRole("button", { name: /create board/i }));
    await waitFor(() => expect(screen.getByRole("combobox", { name: /current board/i })).toHaveValue("2"));
  });
});
