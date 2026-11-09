import { apiRequest } from "./api";

export type SuperAdminAuditEvent = {
  id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type SuperAdminDashboard = {
  users: Record<string, number>;
  organizations: number;
  branches: number;
  services: number;
  counters: number;
  queues: Record<string, number>;
  recent_events: SuperAdminAuditEvent[];
};

export type SuperAdminAuditPage = {
  items: SuperAdminAuditEvent[];
  total: number;
  page: number;
  page_size: number;
};

export type DatabaseBackup = {
  filename: string;
  size_bytes: number;
  created_at: string;
};

export type SuperAdminInitialSetupInput = {
  organization_name: string;
  organization_slug: string;
  branch_name: string;
  branch_address: string | null;
  timezone: string;
  service_name: string;
  service_code: string;
  average_service_minutes: number;
  queue_name: string;
  queue_prefix: string;
};

export type SuperAdminInitialSetupResult = {
  organization_id: string;
  branch_id: string;
  service_id: string;
  queue_id: string;
};

export function getSuperAdminDashboard(token: string) {
  return apiRequest<SuperAdminDashboard>(
    "/api/v1/super-admin/dashboard",
    {},
    token,
  );
}

export function createSuperAdminInitialSetup(
  input: SuperAdminInitialSetupInput,
  token: string,
) {
  return apiRequest<SuperAdminInitialSetupResult>(
    "/api/v1/super-admin/initial-setup",
    { method: "POST", body: JSON.stringify(input) },
    token,
  );
}

export function getSuperAdminAuditLogs(token: string, page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  return apiRequest<SuperAdminAuditPage>(
    `/api/v1/super-admin/audit-logs?${params}`,
    {},
    token,
  );
}

export function getSuperAdminHealth(token: string) {
  return apiRequest<Record<string, string>>(
    "/api/v1/super-admin/system-health",
    {},
    token,
  );
}

export function getSuperAdminBackups(token: string) {
  return apiRequest<DatabaseBackup[]>("/api/v1/super-admin/backups", {}, token);
}

export function createSuperAdminBackup(token: string) {
  return apiRequest<DatabaseBackup>(
    "/api/v1/super-admin/backups",
    { method: "POST" },
    token,
  );
}

export function getSuperAdminWebSocketTicket(token: string) {
  return apiRequest<{ ticket: string }>(
    "/api/v1/super-admin/ws-ticket",
    { method: "POST" },
    token,
  );
}