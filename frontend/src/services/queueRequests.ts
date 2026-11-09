import { apiRequest } from "./api";

export type QueueRequestStatus = "pending" | "approved" | "rejected";

export type QueueRequest = {
  id: string;
  customer: { id: string; full_name: string; email: string };
  branch_id: string;
  branch_name: string;
  request_text: string;
  status: QueueRequestStatus;
  assigned_queue_id: string | null;
  assigned_queue_name: string | null;
  queue_entry_id: string | null;
  queue_number: number | null;
  queue_prefix: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
};

export type QueueRequestPage = {
  items: QueueRequest[];
  total: number;
  pending_total: number;
  page: number;
  page_size: number;
};

export type QueueOption = {
  id: string;
  name: string;
  status: "open" | "paused" | "closed";
};

export function createQueueRequest(
  payload: { branch_id: string; request_text: string },
  token: string,
) {
  return apiRequest<QueueRequest>(
    "/api/v1/customers/queue-requests",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function getMyQueueRequests(token: string) {
  return apiRequest<QueueRequest[]>("/api/v1/customers/queue-requests", {}, token);
}

export function getQueueRequestsForReview(
  token: string,
  status: "pending" | "reviewed" = "pending",
  page = 1,
  pageSize = 50,
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    status,
  });
  return apiRequest<QueueRequestPage>(
    `/api/v1/queue-requests/review?${params}`,
    {},
    token,
  );
}

export function getAdminQueueOptions(token: string) {
  return apiRequest<{
    items: QueueOption[];
    total: number;
    page: number;
    page_size: number;
  }>("/api/v1/admin/queues?page=1&page_size=100", {}, token);
}

export function approveQueueRequest(
  requestId: string,
  queueId: string,
  token: string,
) {
  return apiRequest<QueueRequest>(
    `/api/v1/queue-requests/${encodeURIComponent(requestId)}/approve`,
    { method: "POST", body: JSON.stringify({ queue_id: queueId }) },
    token,
  );
}

export function rejectQueueRequest(
  requestId: string,
  token: string,
  reviewNote?: string,
) {
  return apiRequest<QueueRequest>(
    `/api/v1/queue-requests/${encodeURIComponent(requestId)}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ review_note: reviewNote?.trim() || null }),
    },
    token,
  );
}
