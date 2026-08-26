"use client";

import { useState, type FormEvent } from "react";
import { apiSendJson } from "@/lib/api";
import { type BoardData, applyBoardUpdate } from "@/lib/kanban";

type AIMessage = {
  role: "user" | "assistant";
  text: string;
};

type AIChatPanelProps = {
  board: BoardData;
  boardId: number;
  onBoardUpdate: (board: BoardData) => void;
};

export function AIChatPanel({ board, boardId, onBoardUpdate }: AIChatPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!prompt.trim()) {
      return;
    }

    const userMessage: AIMessage = { role: "user", text: prompt.trim() };
    setMessages((current) => [...current, userMessage]);
    setPrompt("");
    setIsSending(true);
    setError(null);

    try {
      const response = await apiSendJson("/api/ai/chat", "POST", {
        prompt: userMessage.text,
        boardId,
      });

      if (!response.ok) {
        throw new Error(`AI request failed: ${response.status}`);
      }

      const data = await response.json();
      const assistantText = data.message ?? "No response received.";
      setMessages((current) => [...current, { role: "assistant", text: assistantText }]);

      if (data.boardUpdate) {
        onBoardUpdate(applyBoardUpdate(board, data.boardUpdate));
      }
    } catch (requestError) {
      console.error(requestError);
      setError("Unable to reach AI assistant. Try again later.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <aside className="rounded-[32px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)] backdrop-blur">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            AI assistant
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-[var(--navy-dark)]">
            Ask the board
          </h2>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <p className="font-semibold text-slate-900">Tips</p>
          <ul className="list-disc space-y-2 pl-5 text-slate-600">
            <li>Ask to add a card.</li>
            <li>Request a board summary.</li>
            <li>Ask to move cards by status.</li>
          </ul>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700">
            Send a request
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={4}
              className="mt-2 w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
              placeholder="e.g. Create a new card for customer feedback"
            />
          </label>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <button
            type="submit"
            disabled={isSending}
            className="inline-flex h-12 w-full items-center justify-center rounded-3xl bg-[var(--primary-blue)] px-4 text-sm font-semibold text-white transition hover:bg-slate-900 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isSending ? "Sending..." : "Send to AI"}
          </button>
        </form>

        <div className="space-y-3">
          {messages.length ? (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`rounded-3xl border px-4 py-3 text-sm ${
                  message.role === "assistant"
                    ? "border-slate-200 bg-slate-50 text-slate-900"
                    : "border-[var(--primary-blue)] bg-[var(--primary-blue)]/10 text-[var(--navy-dark)]"
                }`}
              >
                <p className="font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                  {message.role === "assistant" ? "Assistant" : "You"}
                </p>
                <p className="mt-2 whitespace-pre-wrap">{message.text}</p>
              </div>
            ))
          ) : (
            <p className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700">
              Start the conversation by asking the AI a board-related question.
            </p>
          )}
        </div>
      </div>
    </aside>
  );
}
