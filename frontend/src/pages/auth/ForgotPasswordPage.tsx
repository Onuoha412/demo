import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { AuthLayout } from "../../components/auth/AuthLayout";
import { ApiError } from "../../services/api";
import { forgotPassword } from "../../services/auth";

export function ForgotPasswordPage({ loginPath = "/login" }: { loginPath?: string }) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const result = await forgotPassword(email);
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.detail : "We could not send the request. Please try again.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthLayout title="Reset your password" subtitle="We’ll send a secure, one-time reset link if an account matches that address.">
      <form className="space-y-4" onSubmit={submit}>
        <label className="block text-sm font-semibold">
          Email address
          <input className="mt-1 w-full rounded-xl border border-ink/15 px-4 py-3" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        {message && <p role="status" className="text-sm text-emerald-800">{message}</p>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded-full bg-ink px-4 py-3 font-bold text-white disabled:opacity-60" disabled={pending}>
          {pending ? "Sending..." : "Send reset link"}
        </button>
      </form>
      <Link to={loginPath} className="mt-5 inline-block text-sm font-semibold text-emerald-700">Back to sign in</Link>
    </AuthLayout>
  );
}
