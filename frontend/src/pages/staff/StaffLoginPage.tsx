import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { login } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import { ApiError } from "../../services/api";
import { PageContainer } from "../../components/common/PageContainer";

export function StaffLoginPage() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((state) => state.setAuth); const navigate = useNavigate(); const location = useLocation();
  const mutation = useMutation({ mutationFn: login, onSuccess: (result) => {
    if (result.user.role !== "staff") { setError("This account is not a staff account."); return; }
    setAuth(result.access_token, result.user); navigate(location.state?.from ?? "/staff/dashboard", { replace: true });
  }});
  const submit = (event: FormEvent) => { event.preventDefault(); if (!email.includes("@") || password.length < 8) { setError("Enter a valid staff email and password."); return; } setError(null); mutation.mutate({ email, password }); };
  return <PageContainer className="max-w-xl py-16"><h1 className="text-4xl font-black">Staff login</h1><form onSubmit={submit} className="mt-8 space-y-4 rounded-2xl bg-white p-6">
    <input aria-label="Email" className="w-full rounded-lg border p-3" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Staff email" />
    <input aria-label="Password" className="w-full rounded-lg border p-3" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
    {(error || mutation.error instanceof ApiError) && <p className="text-sm text-red-600">{error ?? (mutation.error as ApiError).detail}</p>}
    <button className="w-full rounded-full bg-ink px-4 py-3 font-bold text-white" disabled={mutation.isPending}>Sign in</button>
  </form></PageContainer>;
}
