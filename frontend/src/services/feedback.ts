import { apiDownload, apiRequest } from "./api";

export type FeedbackCategory =
  | "general"
  | "bug"
  | "feature_request"
  | "ui_accessibility"
  | "queue_accuracy"
  | "performance_connection"
  | "security_privacy"
  | "account_login"
  | "staff_service"
  | "organization_setup_migration"
  | "notification"
  | "other";

export type FeedbackStatus =
  | "new"
  | "under_review"
  | "planned"
  | "in_progress"
  | "waiting_for_information"
  | "resolved"
  | "declined"
  | "duplicate";

export type FeedbackReply = {
  id: string;
  author_user_id: string | null;
  body: string;
  is_internal: boolean;
  created_at: string;
};

export type FeedbackReport = {
  id: string;
  reporter_user_id: string | null;
  reporter_role: string | null;
  organization_id: string | null;
  branch_id: string | null;
  assigned_to_user_id: string | null;
  duplicate_of_id: string | null;
  category: FeedbackCategory;
  title: string;
  description: string;
  improvement_suggestion: string | null;
  rating: number | null;
  is_anonymous: boolean;
  page_identifier: string | null;
  app_version: string | null;
  status: FeedbackStatus;
  priority: number;
  severity: "low" | "medium" | "high" | "critical";
  reviewed_at: string | null;
  assigned_at: string | null;
  resolved_at: string | null;
  resolution_summary: string | null;
  release_version: string | null;
  resolution_helpful: boolean | null;
  resolution_confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  vote_count: number;
  replies: FeedbackReply[];
  status_history: {
    previous_status: string | null;
    new_status: string;
    created_at: string;
  }[];
};

export type FeedbackPage = {
  items: FeedbackReport[];
  total: number;
  page: number;
  page_size: number;
};

export type FeatureRequest = {
  id: string;
  title: string;
  description: string;
  status: "planned" | "in_progress";
  votes: number;
  voted_by_current_user: boolean;
  created_at: string;
};

export type FeatureRequestPage = {
  items: FeatureRequest[];
  total: number;
  page: number;
  page_size: number;
};

export type FeedbackMetrics = {
  total: number;
  new: number;
  unresolved: number;
  average_rating: number | null;
  resolution_confirmation_rate: number | null;
  average_time_to_first_review_hours: number | null;
  average_resolution_time_hours: number | null;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  by_role: Record<string, number>;
  by_severity: Record<string, number>;
  by_application_area: Record<string, number>;
  by_organization: Record<string, number>;
  by_branch: Record<string, number>;
};

export type FeedbackBranch = { id: string; name: string };
export type FeedbackReviewer = {
  id: string;
  full_name: string;
  role: string;
};

export type FeedbackImprovementTask = {
  id: string;
  title: string;
  description: string;
  acceptance_criteria: string | null;
  priority: number;
  impact: string;
  affected_features: string | null;
  assigned_to_user_id: string | null;
  target_release: string | null;
  release_version: string | null;
  verification_notes: string | null;
  post_release_outcome: string | null;
  status: string;
  created_at: string;
  feedback_report_ids: string[];
};

export type FeedbackImprovementTaskUpdate = {
  status?: string;
  acceptance_criteria?: string | null;
  assigned_to_user_id?: string | null;
  target_release?: string | null;
  release_version?: string | null;
  verification_notes?: string | null;
  post_release_outcome?: string | null;
};

export type FeedbackSubmission = {
  category: FeedbackCategory;
  title: string;
  description: string;
  improvement_suggestion?: string;
  rating?: number;
  is_anonymous: boolean;
  page_identifier: string;
  app_version: string;
  queue_context_entry_id?: string;
  idempotency_key: string;
};

export function submitFeedback(payload: FeedbackSubmission): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMyFeedback(page = 1, pageSize = 20): Promise<FeedbackPage> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiRequest<FeedbackPage>(`/api/v1/feedback/mine?${params}`);
}

export function getManagedFeedback(params: {
  page?: number;
  page_size?: number;
  sort_by?: "newest" | "priority" | "votes";
  status?: FeedbackStatus;
  category?: FeedbackCategory;
  branch_id?: string;
  search?: string;
} = {}): Promise<FeedbackPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  return apiRequest<FeedbackPage>(`/api/v1/feedback/managed?${query}`);
}

export function getFeedbackMetrics(): Promise<FeedbackMetrics> {
  return apiRequest<FeedbackMetrics>("/api/v1/feedback/metrics");
}

export function getFeatureRequests(page = 1): Promise<FeatureRequestPage> {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  return apiRequest<FeatureRequestPage>(`/api/v1/feedback/features?${params}`);
}

export function voteForFeature(reportId: string): Promise<{ voted: boolean; votes: number }> {
  return apiRequest(`/api/v1/feedback/${reportId}/votes`, { method: "POST" });
}

export function removeFeatureVote(reportId: string): Promise<{ voted: boolean; votes: number }> {
  return apiRequest(`/api/v1/feedback/${reportId}/votes`, { method: "DELETE" });
}

export function getFeedbackReviewers(): Promise<FeedbackReviewer[]> {
  return apiRequest<FeedbackReviewer[]>("/api/v1/feedback/reviewers");
}

export function getFeedbackBranches(): Promise<FeedbackBranch[]> {
  return apiRequest<FeedbackBranch[]>("/api/v1/feedback/branches");
}

export function assignFeedback(reportId: string, assignedToUserId: string | null): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/assignment`, {
    method: "PATCH",
    body: JSON.stringify({ assigned_to_user_id: assignedToUserId }),
  });
}

export function updateFeedbackPriority(
  reportId: string,
  priority: number,
  severity: FeedbackReport["severity"],
): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/priority`, {
    method: "PATCH",
    body: JSON.stringify({ priority, severity }),
  });
}

export function getImprovementTasks(): Promise<FeedbackImprovementTask[]> {
  return apiRequest<FeedbackImprovementTask[]>("/api/v1/feedback/tasks");
}

export function createImprovementTask(
  reportId: string,
  payload: {
    title: string;
    description: string;
    priority: number;
    impact: string;
    target_release?: string;
  },
): Promise<{ id: string; title: string; status: string }> {
  return apiRequest(`/api/v1/feedback/${reportId}/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateImprovementTask(
  taskId: string,
  payload: FeedbackImprovementTaskUpdate,
): Promise<{ id: string; title: string; status: string }> {
  return apiRequest(`/api/v1/feedback/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function replyToFeedback(reportId: string, body: string): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/replies`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function addFeedbackNote(reportId: string, body: string): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/notes`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function updateFeedbackStatus(
  reportId: string,
  payload: {
    status: FeedbackStatus;
    note?: string;
    resolution_summary?: string;
    release_version?: string;
  },
): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function confirmFeedbackResolution(
  reportId: string,
  helpful: boolean,
): Promise<FeedbackReport> {
  return apiRequest<FeedbackReport>(`/api/v1/feedback/${reportId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ helpful }),
  });
}

export function exportFeedback(): Promise<Blob> {
  return apiDownload("/api/v1/feedback/export.csv");
}
