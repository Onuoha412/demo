import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { AuthLayout } from "../../components/auth/AuthLayout";
import { ApiError } from "../../services/api";
import { resetPassword, verifyResetToken } from "../../services/auth";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const tokenQuery = useQuery({
    queryKey: ["password-reset-token", token],
    queryFn: () => verifyResetToken(token),
    enabled: token.length >= 32,
    retry: false,
  });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setPending(true);
    try {
      const result = await resetPassword({ token, password });
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.detail : "We could not reset your password. Please try again.");
    } finally {
      setPending(false);
    }
  };

  const valid = token.length >= 32 && tokenQuery.data?.valid;
  return (
    <AuthLayout title="Choose a new password" subtitle="Use a strong password you do not use on another site.">
      {valid ? (
        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm font-semibold">
            New password
            <input className="mt-1 w-full rounded-xl border border-ink/15 px-4 py-3" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <label className="block text-sm font-semibold">
            Confirm new password
            <input className="mt-1 w-full rounded-xl border border-ink/15 px-4 py-3" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
          </label>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          {message && <p role="status" className="text-sm text-emerald-800">{message}</p>}
          {message ? <Link to="/login" className="inline-block font-semibold text-emerald-700">Sign in</Link> : (
            <button className="w-full rounded-full bg-ink px-4 py-3 font-bold text-white disabled:opacity-60" disabled={pending}>{pending ? "Updating..." : "Update password"}</button>
          )}
        </form>
      ) : (
        <div role="status" className="space-y-4 text-sm text-ink/70">
          <p>{tokenQuery.isLoading ? "Checking your secure link..." : tokenQuery.isError ? "This reset link could not be checked." : tokenQuery.data?.reason === "expired" ? "This reset link has expired." : "This reset link is invalid or has already been used."}</p>
          <Link to="/forgot-password" className="inline-block font-semibold text-emerald-700">Request a new link</Link>
        </div>
      )}
    </AuthLayout>
  );
}
