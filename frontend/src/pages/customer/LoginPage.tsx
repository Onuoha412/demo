import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { login, logoutSession } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import { ApiError } from "../../services/api";
import { AuthLayout } from "../../components/auth/AuthLayout";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      if (result.user.role !== "customer") {
        setLoginError("Use the staff or administrator sign-in for this account.");
        void logoutSession(result.session_token).catch((error: unknown) => console.error("Unable to revoke an unsupported session.", error));
        return;
      }
      setAuth(result.user, result.session_token, rememberDevice);
      const redirectTarget = (location.state as { from?: string } | null)?.from ?? searchParams.get("next") ?? "/";
      navigate(redirectTarget, { replace: true });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.includes("@")) {
      setValidationError("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setValidationError("Password must be at least 8 characters.");
      return;
    }
    setValidationError(null);
    setLoginError(null);
    mutation.mutate({ email, password });
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to keep your place and keep moving.">
      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700" htmlFor="login-email">
          Email
          <input
            id="login-email"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="login-password">
          Password
          <div className="relative mt-1">
            <input
              id="login-password"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 pr-12 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute inset-y-0 right-3 flex items-center text-sm font-medium text-slate-500 transition hover:text-slate-700"
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </label>

        <div className="flex items-center justify-between gap-3 text-sm">
          <label className="inline-flex items-center gap-2 text-slate-600">
            <input
              checked={rememberDevice}
              className="h-4 w-4 rounded border-slate-300 text-emerald-700 focus:ring-emerald-500"
              onChange={(event) => setRememberDevice(event.target.checked)}
              type="checkbox"
            />
            Keep me signed in
          </label>
          <Link to="/forgot-password" className="font-semibold text-emerald-700 transition hover:text-emerald-800">
            Forgot password?
          </Link>
        </div>

        {validationError && <p className="text-sm text-red-600">{validationError}</p>}
        {loginError && <p role="alert" className="text-sm text-red-600">{loginError}</p>}
        {mutation.error instanceof ApiError && (
          <p className="text-sm text-red-600">{mutation.error.detail}</p>
        )}

        <button className="w-full rounded-full bg-slate-900 px-4 py-3.5 text-base font-semibold text-white shadow-lg shadow-slate-900/10 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Signing in..." : "Sign in"}
        </button>
      </form>

      <div className="my-5 flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        <span>or</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      <p className="mt-6 text-sm text-slate-600">
        No account yet?{" "}
        <Link to="/register" state={{ from: (location.state as { from?: string } | null)?.from }} className="font-semibold text-emerald-700 transition hover:text-emerald-800">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  );
}
