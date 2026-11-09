import { apiRequest } from "./api";

export type Announcement = {
  id: string;
  organization_id: string | null;
  title: string;
  body: string;
  audience: "all" | "customer" | "staff";
  published_at: string | null;
  expires_at: string | null;
  created_at: string;
};

export type AnnouncementInput = {
  title: string;
  body: string;
  audience: "all" | "customer" | "staff";
  expires_at: string | null;
};

export type PlatformSettings = {
  maintenance_mode: boolean;
  maintenance_message: string;
  updated_at: string | null;
};

export function getPublishedAnnouncements(token: string) {
  return apiRequest<Announcement[]>("/api/v1/announcements", {}, token);
}

export function getAnnouncementWebSocketTicket(token: string) {
  return apiRequest<{ ticket: string }>(
    "/api/v1/auth/announcements-ws-ticket",
    { method: "POST" },
    token,
  );
}

export function getPlatformAnnouncements(token: string) {
  return apiRequest<Announcement[]>(
    "/api/v1/super-admin/announcements",
    {},
    token,
  );
}

export function getOrganizationAnnouncements(token: string) {
  return apiRequest<Announcement[]>(
    "/api/v1/admin/announcements",
    {},
    token,
  );
}

export function createOrganizationAnnouncement(
  input: AnnouncementInput,
  token: string,
) {
  return apiRequest<Announcement>(
    "/api/v1/admin/announcements",
    { method: "POST", body: JSON.stringify(input) },
    token,
  );
}

export function updateOrganizationAnnouncement(
  id: string,
  input: AnnouncementInput,
  token: string,
) {
  return apiRequest<Announcement>(
    `/api/v1/admin/announcements/${id}`,
    { method: "PUT", body: JSON.stringify(input) },
    token,
  );
}

export function setOrganizationAnnouncementPublished(
  id: string,
  published: boolean,
  token: string,
) {
  return apiRequest<Announcement>(
    `/api/v1/admin/announcements/${id}/${published ? "publish" : "unpublish"}`,
    { method: "POST" },
    token,
  );
}

export function createPlatformAnnouncement(
  input: AnnouncementInput,
  token: string,
) {
  return apiRequest<Announcement>(
    "/api/v1/super-admin/announcements",
    { method: "POST", body: JSON.stringify(input) },
    token,
  );
}

export function updatePlatformAnnouncement(
  id: string,
  input: AnnouncementInput,
  token: string,
) {
  return apiRequest<Announcement>(
    `/api/v1/super-admin/announcements/${id}`,
    { method: "PUT", body: JSON.stringify(input) },
    token,
  );
}

export function setAnnouncementPublished(
  id: string,
  published: boolean,
  token: string,
) {
  return apiRequest<Announcement>(
    `/api/v1/super-admin/announcements/${id}/${published ? "publish" : "unpublish"}`,
    { method: "POST" },
    token,
  );
}

export function getPlatformSettings(token: string) {
  return apiRequest<PlatformSettings>(
    "/api/v1/super-admin/platform-settings",
    {},
    token,
  );
}

export function updatePlatformSettings(
  input: Pick<PlatformSettings, "maintenance_mode" | "maintenance_message">,
  token: string,
) {
  return apiRequest<PlatformSettings>(
    "/api/v1/super-admin/platform-settings",
    { method: "PUT", body: JSON.stringify(input) },
    token,
  );
}
