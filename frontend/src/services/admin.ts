import { apiDownload, apiRequest } from "./api";
import type { AdminAnalytics, QueueEntryStatus, QueuePosition } from "../types/api";

export type AdminResource = "organizations" | "branches" | "services" | "counters" | "queues" | "users";
export type AdminPage<T = Record<string, unknown>> = { items: T[]; total: number; page: number; page_size: number };
export type MigrationRow = {
  row_number: number;
  external_id: string | null;
  status: "valid" | "invalid" | "skipped" | "created" | "rejected";
  errors: string[];
};
export type MigrationJob = {
  id: string;
  organization_id: string;
  source_system: string;
  file_sha256: string;
  status: "preview" | "completed" | "failed";
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  created_rows: number;
  skipped_rows: number;
  rejected_rows: number;
  preview_rows: MigrationRow[];
  result_rows: MigrationRow[];
  created_at: string;
  updated_at: string;
};
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

export function getAdminAnalytics(
  token: string,
  start?: string,
  end?: string,
) {
  const params = new URLSearchParams();
  if (start) params.set("start", `${start}T00:00:00Z`);
  if (end) params.set("end", `${end}T23:59:59.999Z`);
  const query = params.size ? `?${params}` : "";
  return apiRequest<AdminAnalytics>(
    `/api/v1/admin/analytics${query}`,
    {},
    token,
  );
}

export function downloadMigrationTemplate(token: string) {
  return apiDownload("/api/v1/admin/migrations/template.csv", token);
}

export function previewAdminMigration(
  token: string,
  file: File,
  sourceSystem: string,
  organizationId?: string,
) {
  const form = new FormData();
  form.set("file", file);
  form.set("source_system", sourceSystem);
  if (organizationId) form.set("organization_id", organizationId);
  return apiRequest<MigrationJob>(
    "/api/v1/admin/migrations/preview",
    { method: "POST", body: form },
    token,
  );
}

export function importAdminMigration(
  token: string,
  jobId: string,
  file: File,
) {
  const form = new FormData();
  form.set("file", file);
  form.set("confirm", "true");
  return apiRequest<MigrationJob>(
    `/api/v1/admin/migrations/${encodeURIComponent(jobId)}/import`,
    { method: "POST", body: form },
    token,
  );
}

export function listAdminMigrations(token: string) {
  return apiRequest<AdminPage<MigrationJob>>(
    "/api/v1/admin/migrations?page=1&page_size=50",
    {},
    token,
  );
}

export function downloadAdminQueueReport(
  token: string,
  start?: string,
  end?: string,
) {
  const params = new URLSearchParams();
  if (start) params.set("start", `${start}T00:00:00Z`);
  if (end) params.set("end", `${end}T23:59:59.999Z`);
  const query = params.size ? `?${params}` : "";
  return apiDownload(`/api/v1/admin/reports/queue-entries.csv${query}`, token);
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

export function listAdminResource(
  resource: AdminResource,
  token: string,
  page = 1,
  pageSize = 20,
  search = "",
  role = "",
  active = "",
  authProvider = "",
) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  if (role) params.set("role", role);
  if (active) params.set("active", active);
  if (authProvider) params.set("auth_provider", authProvider);
  return apiRequest<AdminPage>(`/api/v1/admin/${resource}?${params}`, {}, token);
}

export function approveAdminOrganization(id: string, token: string) {
  return apiRequest<{ organization: Record<string, unknown>; approved_accounts: number }>(
    `/api/v1/admin/organizations/${encodeURIComponent(id)}/approve`,
    { method: "POST" },
    token,
  );
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
