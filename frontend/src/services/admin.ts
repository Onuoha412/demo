import { apiRequest } from "./api";
import type { AdminAnalytics, QueueEntryStatus, QueuePosition } from "../types/api";

export type AdminResource = "organizations" | "branches" | "services" | "counters" | "queues" | "users";
export type AdminPage<T = Record<string, unknown>> = { items: T[]; total: number; page: number; page_size: number };
export type AdminQueueAudit = {
  id: string;
  name: string;
  prefix: string;
  status: "open" | "paused" | "closed";
  service_id: string;
  service_name: string;
  branch_id: string;
  total_entries: number;
  page: number;
  page_size: number;
  entries: (QueuePosition & {
    status: QueueEntryStatus;
    customer: { id: string; full_name: string; email: string };
  })[];
};

export function getAdminAnalytics(token: string) {
  return apiRequest<AdminAnalytics>("/api/v1/admin/analytics", {}, token);
}

export function getAdminQueueAudit(queueId: string, token: string, page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  return apiRequest<AdminQueueAudit>(
    `/api/v1/admin/queues/${encodeURIComponent(queueId)}/entries?${params}`,
    {},
    token,
  );
}

export function verifyAdminQueueEntry(entryId: string, token: string) {
  return apiRequest(
    `/api/v1/admin/queue-entries/${encodeURIComponent(entryId)}/verify`,
    { method: "POST" },
    token,
  );
}

export function listAdminResource(resource: AdminResource, token: string, page = 1, pageSize = 20, search = "", role = "") {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  if (role) params.set("role", role);
  return apiRequest<AdminPage>(`/api/v1/admin/${resource}?${params}`, {}, token);
}

export function createAdminResource(resource: AdminResource, payload: Record<string, unknown>, token: string) {
  return apiRequest(`/api/v1/admin/${resource}`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export function updateAdminResource(resource: AdminResource, id: string, payload: Record<string, unknown>, token: string) {
  return apiRequest(`/api/v1/admin/${resource}/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
}

export function setAdminResourceActive(resource: AdminResource, id: string, active: boolean, token: string) {
  return apiRequest(`/api/v1/admin/${resource}/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }, token);
}

export function setAdminQueueStatus(id: string, status: "open" | "paused" | "closed", token: string) {
  return apiRequest(`/api/v1/admin/queues/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }, token);
}
