import { apiRequest, ApiError } from "./api";
import { useAuthStore } from "../store/authStore";
import type { AuthResponse, User } from "../types/api";

export type RegisterPayload = {
  full_name: string;
  email: string;
  password: string;
  requested_role?: "customer" | "staff" | "admin";
  organization_id?: string | null;
  organization_name?: string | null;
  branch_id?: string | null;
};

export type PendingOrganizationApproval = {
  status: "pending_approval";
  email: string;
  organization_name: string;
  message: string;
};

export type RegisterResponse = AuthResponse | PendingOrganizationApproval;

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: { email: string; password: string }): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function me(sessionToken?: string): Promise<User> {
  return apiRequest<User>("/api/v1/auth/me", {}, sessionToken);
}

export async function updateProfile(fullName: string): Promise<User> {
  return apiRequest<User>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ full_name: fullName }),
  });
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<{ message: string }> {
  return apiRequest("/api/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logoutSession(sessionToken?: string): Promise<void> {
  await apiRequest<void>("/api/v1/auth/logout", { method: "POST" }, sessionToken);
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return apiRequest("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyResetToken(token: string): Promise<{ valid: boolean; reason?: string }> {
  return apiRequest(`/api/v1/auth/verify-reset-token?${new URLSearchParams({ token })}`);
}

export async function resetPassword(payload: { token: string; password: string }): Promise<{ message: string }> {
  return apiRequest("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function handleAuthError(error: unknown): never {
  if (error instanceof ApiError && error.status === 401) {
    useAuthStore.getState().logout();
    throw new ApiError(401, "Your session expired. Please sign in again.");
  }
  throw error;
}
