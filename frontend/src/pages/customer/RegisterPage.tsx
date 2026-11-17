import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../services/api";
import { register } from "../../services/auth";
import { getBranches, getOrganizations } from "../../services/queue";
import { useAuthStore } from "../../store/authStore";
import { AuthLayout } from "../../components/auth/AuthLayout";
import { PasswordInput } from "../../components/common/PasswordInput";
import { roleHomePath } from "../../utils/roleRoutes";

type RegistrationRole = "customer" | "staff" | "admin";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [registrationRole, setRegistrationRole] = useState<RegistrationRole>(() => {
    const role = searchParams.get("role");
    return role === "staff" || role === "admin" ? role : "customer";
  });
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [rememberDevice, setRememberDevice] = useState(false);
  const [organizationName, setOrganizationName] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [branchId, setBranchId] = useState("");
  const organizations = useQuery({
    queryKey: ["registration", "organizations"],
    queryFn: getOrganizations,
    enabled: registrationRole !== "customer",
  });
  const branches = useQuery({
    queryKey: ["registration", "branches", organizationId],
    queryFn: () => getBranches(organizationId),
    enabled: registrationRole === "staff" && Boolean(organizationId),
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [pendingApprovalMessage, setPendingApprovalMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      if (!("session_token" in result)) {
        setPendingApprovalMessage(result.message);
        return;
      }
      if (result.user.role !== registrationRole) {
        setValidationError("Registration returned an unexpected account type.");
        return;
      }
      setAuth(result.user, result.session_token, rememberDevice);
      const redirectTarget =
        (location.state as { from?: string } | null)?.from ??
        searchParams.get("next") ??
        (registrationRole === "customer" ? "/services" : roleHomePath(registrationRole));
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
    if (registrationRole === "staff" && (!organizationId || !branchId)) {
      setValidationError("Choose your organization and assigned branch.");
      return;
    }
    if (
      registrationRole === "admin" &&
      !organizationId &&
      !organizationName.trim()
    ) {
      setValidationError("Choose your organization or request a new one.");
      return;
    }
    setValidationError(null);
    setPendingApprovalMessage(null);
    mutation.mutate({
      full_name: fullName,
      email,
      password,
      requested_role: registrationRole,
      organization_id:
        organizationId && organizationId !== "new" ? organizationId : null,
      organization_name:
        registrationRole === "customer" || organizationId === "new"
          ? organizationName.trim() || null
          : null,
      branch_id: registrationRole === "staff" ? branchId : null,
    });
  };

  return (
    <AuthLayout
      title={registrationRole === "customer" ? "Create your account" : "Request an account"}
      subtitle={
        registrationRole === "customer"
          ? "Join QueueLess and skip unnecessary waiting."
          : "Your account will be enabled after the appropriate administrator approves your request."
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700" htmlFor="register-role">
          Account type
          <select
            id="register-role"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm"
            value={registrationRole}
            onChange={(event) => {
              const value = event.target.value;
              if (value !== "customer" && value !== "staff" && value !== "admin") {
                return;
              }
              setRegistrationRole(value);
              setOrganizationId("");
              setBranchId("");
              setOrganizationName("");
              setValidationError(null);
              setPendingApprovalMessage(null);
            }}
          >
            <option value="customer">Customer</option>
            <option value="staff">Staff member</option>
            <option value="admin">Organization administrator</option>
          </select>
        </label>

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

        {registrationRole === "customer" ? (
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
              New organizations need Super Admin approval before members can sign in.
            </span>
          </label>
        ) : (
          <>
            <label className="block text-sm font-semibold text-slate-700" htmlFor="register-organization">
              Organization
              <select
                id="register-organization"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm"
                value={organizationId}
                onChange={(event) => {
                  setOrganizationId(event.target.value);
                  setBranchId("");
                  setOrganizationName("");
                  setPendingApprovalMessage(null);
                }}
                required
              >
                <option value="">
                  {organizations.isLoading ? "Loading organizations..." : "Select your organization"}
                </option>
                {organizations.data?.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
                {registrationRole === "admin" && (
                  <option value="new">Request a new organization</option>
                )}
              </select>
            </label>
            {organizations.isError && (
              <p className="text-sm text-red-600" role="alert">
                Organizations could not be loaded.{" "}
                <button className="font-bold underline" onClick={() => void organizations.refetch()} type="button">
                  Retry
                </button>
              </p>
            )}
            {organizationId === "new" && (
              <label className="block text-sm font-semibold text-slate-700" htmlFor="register-new-organization">
                New organization name
                <input
                  id="register-new-organization"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm"
                  autoComplete="organization"
                  maxLength={160}
                  value={organizationName}
                  onChange={(event) => setOrganizationName(event.target.value)}
                  required
                />
              </label>
            )}
            {registrationRole === "staff" && organizationId && (
              <label className="block text-sm font-semibold text-slate-700" htmlFor="register-branch">
                Branch
                <select
                  id="register-branch"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-900 shadow-sm"
                  value={branchId}
                  onChange={(event) => setBranchId(event.target.value)}
                  required
                >
                  <option value="">
                    {branches.isLoading ? "Loading branches..." : "Select your branch"}
                  </option>
                  {branches.data?.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </select>
                {branches.isError && (
                  <span className="mt-1 block text-sm font-normal text-red-600">
                    Branches could not be loaded. Change the organization or retry.
                  </span>
                )}
              </label>
            )}
            <p className="text-xs text-slate-500">
              {registrationRole === "staff"
                ? "An organization administrator must approve your staff account."
                : organizationId === "new"
                  ? "A Super Admin must approve the organization and administrator account."
                  : "A Super Admin must approve your administrator account."}
            </p>
          </>
        )}
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
          {mutation.isPending
            ? "Submitting request..."
            : registrationRole === "customer"
              ? "Create account"
              : registrationRole === "staff"
                ? "Request staff account"
                : "Request administrator account"}
        </button>
      </form>

      <p className="mt-6 text-sm text-slate-600">
        Already have an account?{" "}
        <Link to="/login" state={{ from: (location.state as { from?: string } | null)?.from }} className="font-semibold text-emerald-700 transition hover:text-emerald-800">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
