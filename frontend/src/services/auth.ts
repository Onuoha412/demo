import { apiRequest, ApiError } from "./api";
import { useAuthStore } from "../store/authStore";
import type { AuthResponse, User } from "../types/api";

export type RegisterPayload = {
  full_name: string;
  email: string;
  password: string;
  organization_id?: string | null;
};

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/api/v1/auth/register", {
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

export async function me(token: string): Promise<User> {
  return apiRequest<User>("/api/v1/auth/me", {}, token);
}

export function handleAuthError(error: unknown): never {
  if (error instanceof ApiError && error.status === 401) {
    useAuthStore.getState().logout();
    throw new ApiError(401, "Your session expired. Please sign in again.");
  }
  throw error;
}
