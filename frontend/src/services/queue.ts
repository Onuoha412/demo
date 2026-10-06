import { apiRequest } from "./api";
import { handleAuthError } from "./auth";
import { useAuthStore } from "../store/authStore";
import type {
  Branch,
  Organization,
  QueueHistoryResponse,
  QueuePosition,
  Service,
} from "../types/api";

function requireToken() {
  const token = useAuthStore.getState().token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

export async function getOrganizations(): Promise<Organization[]> {
  return apiRequest<Organization[]>("/api/v1/catalog/organizations");
}

export async function getBranches(organizationId?: string): Promise<Branch[]> {
  const query = organizationId ? `?organization_id=${organizationId}` : "";
  return apiRequest<Branch[]>(`/api/v1/catalog/branches${query}`);
}

export async function getServices(branchId?: string): Promise<Service[]> {
  const query = branchId ? `?branch_id=${branchId}` : "";
  return apiRequest<Service[]>(`/api/v1/catalog/services${query}`);
}

export async function getService(serviceId: string): Promise<Service> {
  return apiRequest<Service>(`/api/v1/catalog/services/${serviceId}`);
}

export async function getQueue(queueId: string) {
  return apiRequest<{
    id: string; name: string; prefix: string; status: "open" | "paused" | "closed";
    entries: QueuePosition[];
  }>(`/api/v1/queues/${queueId}?page=1&page_size=20`);
}

export async function joinService(serviceId: string, branchId?: string): Promise<QueuePosition> {
  try {
    const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
    return await apiRequest<QueuePosition>(
      `/api/v1/customers/services/${encodeURIComponent(serviceId)}/join${query}`,
      { method: "POST" },
      requireToken(),
    );
  } catch (error) {
    handleAuthError(error);
  }
}

export async function getQueueEntry(entryId: string): Promise<QueuePosition> {
  try {
    return await apiRequest<QueuePosition>(
      `/api/v1/customers/queue-entries/${entryId}`,
      {},
      requireToken(),
    );
  } catch (error) {
    handleAuthError(error);
  }
}

export async function getHistory(page = 1, pageSize = 20): Promise<QueueHistoryResponse> {
  try {
    return await apiRequest<QueueHistoryResponse>(
      `/api/v1/customers/history?page=${page}&page_size=${pageSize}`,
      {},
      requireToken(),
    );
  } catch (error) {
    handleAuthError(error);
  }
}
