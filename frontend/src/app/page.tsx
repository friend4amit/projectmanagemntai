"use client";

import { useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm, type AuthenticatedUser } from "@/components/LoginForm";

export default function Home() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      try {
        const response = await fetch("/api/auth/me");
        if (response.ok) {
          setUser(await response.json());
        }
      } finally {
        setIsCheckingSession(false);
      }
    };
    void restoreSession();
  }, []);

  if (isCheckingSession) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-700">Loading...</div>;
  }

  return user ? (
    <KanbanBoard user={user} onLogout={() => setUser(null)} />
  ) : (
    <LoginForm onLogin={setUser} />
  );
}
