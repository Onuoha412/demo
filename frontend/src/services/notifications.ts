import { apiRequest } from "./api";
import { handleAuthError } from "./auth";
import { useAuthStore } from "../store/authStore";

export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  queue_entry_id: string | null;
};

export type NotificationPreferences = {
  enabled: boolean;
  joined: boolean;
  called: boolean;
  approaching: boolean;
  completed: boolean;
  queue_updates: boolean;
};

function token() {
  const value = useAuthStore.getState().token;
  if (!value) throw new Error("Not authenticated");
  return value;
}

export async function getNotifications(page = 1): Promise<{ items: NotificationItem[]; total: number; unread_count: number }> {
  try {
    const [response, unread] = await Promise.all([
      apiRequest<{ items: NotificationItem[]; total: number }>(`/api/v1/notifications?page=${page}&page_size=20`, {}, token()),
      apiRequest<{ count: number }>("/api/v1/notifications/unread-count", {}, token()),
    ]);
    return { ...response, unread_count: unread.count };
  } catch (error) { handleAuthError(error); }
}

export async function markNotificationRead(id: string) {
  try { return await apiRequest(`/api/v1/notifications/${id}/read`, { method: "POST" }, token()); } catch (error) { handleAuthError(error); }
}

export async function markAllNotificationsRead() {
  try { return await apiRequest("/api/v1/notifications/read-all", { method: "POST" }, token()); } catch (error) { handleAuthError(error); }
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  try { return await apiRequest<NotificationPreferences>("/api/v1/notifications/preferences", {}, token()); } catch (error) { handleAuthError(error); }
}

export async function updateNotificationPreferences(payload: NotificationPreferences): Promise<NotificationPreferences> {
  try { return await apiRequest<NotificationPreferences>("/api/v1/notifications/preferences", { method: "PUT", body: JSON.stringify(payload) }, token()); } catch (error) { handleAuthError(error); }
}
