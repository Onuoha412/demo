import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../services/api";
import { register } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import { AuthLayout } from "../../components/auth/AuthLayout";
import { PasswordInput } from "../../components/common/PasswordInput";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [rememberDevice, setRememberDevice] = useState(false);
  const [organizationName, setOrganizationName] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [pendingApprovalMessage, setPendingApprovalMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      if (!("session_token" in result)) {
        setPendingApprovalMessage(result.message);
        return;
      }
      if (result.user.role !== "customer") {
        setValidationError("Customer registration returned an unsupported account type.");
        return;
      }
      setAuth(result.user, result.session_token, rememberDevice);
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
      organization_name: organizationName.trim() || null,
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
          <PasswordInput
            id="register-password"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-confirm-password">
          Confirm password
          <PasswordInput
            id="register-confirm-password"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-organization">
          Organization (optional)
          <input
            id="register-organization"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm transition focus:border-emerald-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-100"
            autoComplete="organization"
            maxLength={160}
            value={organizationName}
            onChange={(event) => {
              setOrganizationName(event.target.value);
              setPendingApprovalMessage(null);
            }}
          />
          <span className="mt-1 block text-xs font-normal text-slate-500">
            New organizations need administrator approval before their members can sign in.
          </span>
        </label>
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <input
            checked={rememberDevice}
            className="h-4 w-4 rounded border-slate-300 text-emerald-700 focus:ring-emerald-500"
            onChange={(event) => setRememberDevice(event.target.checked)}
            type="checkbox"
          />
          Keep me signed in on this device
        </label>

        {validationError && <p role="alert" className="text-sm text-red-600">{validationError}</p>}
        {mutation.error instanceof ApiError && <p className="text-sm text-red-600">{mutation.error.detail}</p>}

        {pendingApprovalMessage && (
          <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
            {pendingApprovalMessage}
          </p>
        )}

        <button className="w-full rounded-full bg-slate-900 px-4 py-3.5 text-base font-semibold text-white shadow-lg shadow-slate-900/10 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating account..." : "Create account"}
        </button>
      </form>

      {organizationName.trim() ? (
        <p className="mt-5 text-center text-sm text-slate-500">
          Use the registration form so your organization is linked to your account.
        </p>
      ) : (
        <>
          <div className="my-5 flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-slate-400">
            <span className="h-px flex-1 bg-slate-200" />
            <span>or</span>
            <span className="h-px flex-1 bg-slate-200" />
          </div>
        </>
      )}

      <p className="mt-6 text-sm text-slate-600">
        Already have an account?{" "}
        <Link to="/login" state={{ from: (location.state as { from?: string } | null)?.from }} className="font-semibold text-emerald-700 transition hover:text-emerald-800">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
