"use client";

import { useState, type FormEvent } from "react";

export type AuthenticatedUser = {
  id: number;
  username: string;
};

type LoginFormProps = {
  onLogin: (user: AuthenticatedUser) => void;
};

export function LoginForm({ onLogin }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(isRegistering ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Unable to sign in.");
      }
      onLogin(await response.json());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to sign in.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const switchMode = () => {
    setIsRegistering((current) => !current);
    setError(null);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-10 shadow-lg">
        <h1 className="text-3xl font-semibold text-slate-900">{isRegistering ? "Create account" : "Sign in"}</h1>
        <p className="mt-2 text-sm text-slate-500">
          {isRegistering ? "Create a local account to keep your boards separate." : "Sign in to your local workspace. Default login: user / password."}
        </p>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              Username
              <input className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus:border-slate-400 focus:outline-none" value={username} onChange={(event) => setUsername(event.target.value)} required />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Password
              <input type="password" className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus:border-slate-400 focus:outline-none" value={password} onChange={(event) => setPassword(event.target.value)} required />
            </label>
          </div>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <button type="submit" disabled={isSubmitting} className="w-full rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-400">
            {isSubmitting ? "Please wait..." : isRegistering ? "Create account" : "Sign in"}
          </button>
        </form>
        <button type="button" onClick={switchMode} className="mt-5 w-full text-sm font-semibold text-[var(--primary-blue)] hover:text-[var(--navy-dark)]">
          {isRegistering ? "Already have an account? Sign in" : "Need an account? Create one"}
        </button>
      </div>
    </div>
  );
}
