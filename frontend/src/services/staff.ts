import { apiRequest } from "./api";
import type { QueuePosition, StaffDashboard } from "../types/api";
import { captureProductEvent } from "../observability";

type StaffAction = "call" | "start" | "complete" | "skip";
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

export function staffAction(entryId: string, action: StaffAction, token: string, counterId?: string) {
  return apiRequest<QueuePosition>(`/api/v1/queue-entries/${entryId}/${action}`, {
    method: "POST",
    body: JSON.stringify(counterId ? { counter_id: counterId } : {}),
  }, token).then((result) => {
    captureProductEvent(staffActionEvents[action]);
    return result;
  });
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
