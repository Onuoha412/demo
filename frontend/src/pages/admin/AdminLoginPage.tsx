import { useCallback, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { AuthLayout } from "../../components/auth/AuthLayout";
import { PasswordInput } from "../../components/common/PasswordInput";
import { ApiError } from "../../services/api";
import { login, logoutSession } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import type { AuthResponse } from "../../types/api";

export function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberDevice, setRememberDevice] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();
  const location = useLocation();
  const handleAuthenticated = useCallback((result: AuthResponse) => {
    if (result.user.role !== "admin") {
      setError("This account is not an administrator.");
      void logoutSession(result.session_token).catch((logoutError: unknown) =>
        console.error("Unable to revoke an unsupported session.", logoutError),
      );
      return false;
    }
    setAuth(result.user, result.session_token, rememberDevice);
    navigate(location.state?.from ?? "/admin/dashboard", { replace: true });
    return true;
  }, [location.state, navigate, rememberDevice, setAuth]);
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: handleAuthenticated,
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
        <label className="inline-flex items-center gap-2 text-sm text-ink/70">
          <input checked={rememberDevice} onChange={(event) => setRememberDevice(event.target.checked)} type="checkbox" />
          Keep me signed in
        </label>
        <label className="block text-sm font-semibold">
          Password
          <PasswordInput aria-label="Password" autoComplete="current-password" className="mt-1 w-full rounded-xl border border-ink/15 p-3" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {(error || mutation.error instanceof ApiError) && <p role="alert" className="text-sm text-red-600">{error ?? mutation.error?.message}</p>}
        <button className="w-full rounded-full bg-ink px-4 py-3 font-bold text-white disabled:opacity-60" disabled={mutation.isPending}>{mutation.isPending ? "Signing in..." : "Sign in"}</button>
        <Link to="/admin/forgot-password" className="block text-center text-sm font-semibold text-emerald-700">Forgot password?</Link>
      </form>
      <div className="my-5 flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        <span>or</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>
      <Link to="/register?role=admin" className="mt-5 inline-block text-sm font-semibold text-emerald-700">
        Request an administrator account
      </Link>
    </AuthLayout>
  );
}
