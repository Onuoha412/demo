import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../services/api";
import { logoutSession, register } from "../../services/auth";
import { getOrganizations } from "../../services/queue";
import { useAuthStore } from "../../store/authStore";
import { AuthLayout } from "../../components/auth/AuthLayout";
import { GoogleSignInButton } from "../../components/auth/GoogleSignInButton";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [organizationId, setOrganizationId] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleGoogleAuthenticated = useCallback((result: Awaited<ReturnType<typeof register>>) => {
    if (result.user.role !== "customer") {
      setValidationError("Use the staff or administrator sign-in for this account.");
      void logoutSession(result.session_token).catch((error: unknown) =>
        console.error("Unable to revoke an unsupported session.", error),
      );
      return;
    }
    setAuth(result.user, result.session_token);
    const redirectTarget =
      (location.state as { from?: string } | null)?.from ??
      searchParams.get("next") ??
      "/services";
    navigate(redirectTarget, { replace: true });
  }, [location.state, navigate, searchParams, setAuth]);

  const organizationsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
  });

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      if (result.user.role !== "customer") {
        setValidationError("Customer registration returned an unsupported account type.");
        return;
      }
      setAuth(result.user, result.session_token);
      const redirectTarget = (location.state as { from?: string } | null)?.from ?? searchParams.get("next") ?? "/services";
      navigate(redirectTarget, { replace: true });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (fullName.trim().length < 2) {
      setValidationError("Please enter your full name.");
      return;
    }
    if (!email.includes("@")) {
      setValidationError("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setValidationError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setValidationError("Passwords do not match.");
      return;
    }
    setValidationError(null);
    mutation.mutate({
      full_name: fullName,
      email,
      password,
      organization_id: organizationId || null,
    });
  };

  return (
    <AuthLayout title="Create your account" subtitle="Join QueueLess and skip unnecessary waiting.">
      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-name">
          Full name
          <input
            id="register-name"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-email">
          Email
          <input
            id="register-email"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-password">
          Password
          <div className="relative mt-1">
            <input
              id="register-password"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 pr-12 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
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

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-confirm-password">
          Confirm password
          <input
            id="register-confirm-password"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-organization">
          Organization (optional)
          <select
            id="register-organization"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            value={organizationId}
            onChange={(event) => setOrganizationId(event.target.value)}
          >
            <option value="">Select organization</option>
            {(organizationsQuery.data ?? []).map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </select>
        </label>

        {validationError && <p className="text-sm text-red-600">{validationError}</p>}
        {mutation.error instanceof ApiError && <p className="text-sm text-red-600">{mutation.error.detail}</p>}

        <button className="w-full rounded-full bg-slate-900 px-4 py-3.5 text-base font-semibold text-white shadow-lg shadow-slate-900/10 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating account..." : "Create account"}
        </button>
      </form>

      <div className="my-5 flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        <span>or</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      <GoogleSignInButton onAuthenticated={handleGoogleAuthenticated} />

      <p className="mt-6 text-sm text-slate-600">
        Already have an account?{" "}
        <Link to="/login" state={{ from: (location.state as { from?: string } | null)?.from }} className="font-semibold text-emerald-700 transition hover:text-emerald-800">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
