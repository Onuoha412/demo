import { apiRequest } from "./api";
import type { QueuePosition, StaffDashboard } from "../types/api";
import { captureProductEvent } from "../observability";

type StaffAction = "call" | "start" | "complete" | "skip";
export type StaffCustomerRecord = {
  entry_id: string;
  queue_id: string;
  queue_name: string;
  queue_prefix: string;
  queue_number: number;
  status: QueuePosition["status"];
  joined_at: string;
  customer: { id: string; full_name: string; email: string };
};
export type StaffHistoryRecord = StaffCustomerRecord & {
  queue_id: string;
  queue_name: string;
  completed_at: string | null;
};

const staffActionEvents: Record<StaffAction, Parameters<typeof captureProductEvent>[0]> = {
  call: "queue_called",
  start: "queue_started",
  complete: "queue_completed",
  skip: "queue_skipped",
};

export function getStaffDashboard(token: string) {
  return apiRequest<StaffDashboard>("/api/v1/staff/dashboard", {}, token);
}

export function getStaffQueue(queueId: string, token: string) {
  return apiRequest<{ entries: QueuePosition[]; id: string; name: string; status: string }>(
    `/api/v1/staff/queues/${queueId}`,
    {},
    token,
  );
}

export function getStaffCustomers(token: string) {
  return apiRequest<StaffCustomerRecord[]>("/api/v1/staff/customers", {}, token);
}

export function getStaffHistory(token: string) {
  return apiRequest<StaffHistoryRecord[]>("/api/v1/staff/history", {}, token);
}

export function staffAction(entryId: string, action: StaffAction, token: string, counterId?: string) {
  return apiRequest<QueuePosition>(`/api/v1/queue-entries/${entryId}/${action}`, {
    method: "POST",
    body: JSON.stringify(counterId ? { counter_id: counterId } : {}),
  }, token).then((result) => {
    captureProductEvent(staffActionEvents[action]);
    return result;
  });
}

export function setStaffEntryPriority(
  entryId: string,
  priority: number,
  token: string,
) {
  return apiRequest<QueuePosition>(
    `/api/v1/queue-entries/${encodeURIComponent(entryId)}/priority`,
    { method: "POST", body: JSON.stringify({ priority }) },
    token,
  );
}

export function transferStaffQueueEntry(
  entryId: string,
  targetQueueId: string,
  token: string,
) {
  return apiRequest<QueuePosition>(
    `/api/v1/queue-entries/${encodeURIComponent(entryId)}/transfer`,
    {
      method: "POST",
      body: JSON.stringify({ target_queue_id: targetQueueId }),
    },
    token,
  );
}

export function nextCustomer(queueId: string, token: string, counterId?: string) {
  return apiRequest<QueuePosition>(`/api/v1/queues/${queueId}/next`, {
    method: "POST",
    body: JSON.stringify(counterId ? { counter_id: counterId } : {}),
  }, token).then((result) => {
    captureProductEvent("queue_called");
    return result;
  });
}

export function setQueueStatus(queueId: string, status: "pause" | "resume", token: string) {
  return apiRequest(`/api/v1/staff/queues/${queueId}/${status}`, { method: "POST" }, token);
}
