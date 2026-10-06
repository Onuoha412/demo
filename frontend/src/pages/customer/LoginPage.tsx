import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { login } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import { ApiError } from "../../services/api";
import { PageContainer } from "../../components/common/PageContainer";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      setAuth(result.access_token, result.user);
      navigate(location.state?.from ?? "/services", { replace: true });
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
    mutation.mutate({ email, password });
  };

  return (
    <PageContainer className="max-w-xl py-16">
      <h1 className="text-4xl font-black text-ink">Login</h1>
      <form className="mt-8 space-y-4 rounded-2xl border border-ink/10 bg-white p-6" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-ink">
          Email
          <input
            className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-semibold text-ink">
          Password
          <input
            className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {validationError && <p className="text-sm text-red-600">{validationError}</p>}
        {mutation.error instanceof ApiError && (
          <p className="text-sm text-red-600">{mutation.error.detail}</p>
        )}
        <button className="w-full rounded-full bg-ink px-4 py-3 text-white" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Signing in..." : "Sign in"}
        </button>
      </form>
      <p className="mt-4 text-sm text-ink/70">
        No account yet?{" "}
        <Link to="/register" state={{ from: location.state?.from }} className="font-semibold text-emerald-700">
          Register
        </Link>
      </p>
    </PageContainer>
  );
}
