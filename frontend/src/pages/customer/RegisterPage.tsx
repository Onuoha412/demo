import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../services/api";
import { register } from "../../services/auth";
import { getOrganizations } from "../../services/queue";
import { useAuthStore } from "../../store/authStore";
import { PageContainer } from "../../components/common/PageContainer";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationId, setOrganizationId] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const organizationsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
  });

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      setAuth(result.access_token, result.user);
      navigate(location.state?.from ?? "/services", { replace: true });
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
    setValidationError(null);
    mutation.mutate({
      full_name: fullName,
      email,
      password,
      organization_id: organizationId || null,
    });
  };

  return (
    <PageContainer className="max-w-xl py-16">
      <h1 className="text-4xl font-black text-ink">Register</h1>
      <form className="mt-8 space-y-4 rounded-2xl border border-ink/10 bg-white p-6" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-ink">
          Full name
          <input className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
        </label>
        <label className="block text-sm font-semibold text-ink">
          Email
          <input className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="block text-sm font-semibold text-ink">
          Password
          <input className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        <label className="block text-sm font-semibold text-ink">
          Organization (optional)
          <select className="mt-1 w-full rounded-lg border border-ink/20 px-3 py-2" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
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
        <button className="w-full rounded-full bg-ink px-4 py-3 text-white" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating account..." : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm text-ink/70">
        Already have an account?{" "}
        <Link to="/login" state={{ from: location.state?.from }} className="font-semibold text-emerald-700">
          Login
        </Link>
      </p>
    </PageContainer>
  );
}
