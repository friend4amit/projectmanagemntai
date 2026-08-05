"use client";

import { useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    setIsAuthenticated(localStorage.getItem("pm-user-auth") === "true");
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("pm-user-auth");
    setIsAuthenticated(false);
  };

  return isAuthenticated ? (
    <KanbanBoard onLogout={handleLogout} />
  ) : (
    <LoginForm onLogin={() => setIsAuthenticated(true)} />
  );
}
