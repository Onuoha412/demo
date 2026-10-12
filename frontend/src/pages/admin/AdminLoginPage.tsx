import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import { AuthLayout } from "../../components/auth/AuthLayout";
import { ApiError } from "../../services/api";
import { login, logoutSession } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";

export function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();
  const location = useLocation();
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      if (result.user.role !== "admin") {
        setError("This account is not an administrator.");
        void logoutSession(result.session_token).catch((logoutError: unknown) => console.error("Unable to revoke an unsupported session.", logoutError));
        return;
      }
      setAuth(result.user, result.session_token);
      navigate(location.state?.from ?? "/admin/dashboard", { replace: true });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.includes("@") || password.length < 8) {
      setError("Enter a valid administrator email and password.");
      return;
    }
    setError(null);
    mutation.mutate({ email, password });
  };

  return (
    <AuthLayout title="Administrator sign in" subtitle="Manage QueueLess organizations, services, and teams.">
      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-semibold">
          Email
          <input aria-label="Email" autoComplete="username" className="mt-1 w-full rounded-xl border border-ink/15 p-3" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="block text-sm font-semibold">
          Password
          <input aria-label="Password" autoComplete="current-password" className="mt-1 w-full rounded-xl border border-ink/15 p-3" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {(error || mutation.error instanceof ApiError) && <p role="alert" className="text-sm text-red-600">{error ?? mutation.error?.message}</p>}
        <button className="w-full rounded-full bg-ink px-4 py-3 font-bold text-white disabled:opacity-60" disabled={mutation.isPending}>{mutation.isPending ? "Signing in..." : "Sign in"}</button>
      </form>
    </AuthLayout>
  );
}
