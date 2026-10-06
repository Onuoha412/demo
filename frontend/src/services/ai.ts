import { apiRequest } from "./api";
import { handleAuthError } from "./auth";
import { useAuthStore } from "../store/authStore";
import type { WaitTimePrediction } from "../types/api";

export async function getWaitTimePrediction(entryId: string): Promise<WaitTimePrediction> {
  const token = useAuthStore.getState().token;
  if (!token) throw new Error("Not authenticated");
  try {
    return await apiRequest<WaitTimePrediction>(`/api/v1/ai/wait-time/${entryId}`, {}, token);
  } catch (error) {
    handleAuthError(error);
  }
}
