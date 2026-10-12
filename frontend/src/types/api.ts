export type User = {
  id: string;
  full_name: string;
  email: string;
  role: "customer" | "staff" | "admin";
  organization_id: string | null;
  branch_id?: string | null;
  created_at: string;
};

export type StaffCounter = { id: string; name: string; number: number; status: string };
export type StaffQueueSummary = {
  id: string;
  name: string;
  prefix: string;
  status: "open" | "paused" | "closed";
  waiting_count: number;
  serving_count: number;
  completed_count: number;
  skipped_count: number;
};
export type StaffDashboard = {
  branch: { id: string; name: string } | null;
  counters: StaffCounter[];
  queues: StaffQueueSummary[];
};

export type AuthResponse = {
  user: User;
  session_token: string;
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
};

export type Branch = {
  id: string;
  organization_id: string;
  name: string;
  address: string | null;
  timezone: string;
};

export type Service = {
  id: string;
  branch_id: string;
  name: string;
  code: string;
  description: string | null;
  average_service_minutes: number;
  queue_id: string | null;
};

export type QueueEntryStatus =
  | "waiting"
  | "called"
  | "serving"
  | "completed"
  | "skipped"
  | "cancelled";

export type QueuePosition = {
  id: string;
  queue_id?: string;
  queue_prefix: string;
  queue_number: number;
  status: QueueEntryStatus;
  people_ahead: number;
  estimated_wait_minutes: number;
  counter_id: string | null;
  counter: { id: string; name: string; number: number; status: string } | null;
  joined_at: string;
  called_at: string | null;
  service_started_at: string | null;
  completed_at: string | null;
  request_note?: string | null;
  verified_at?: string | null;
  verified_by_user_id?: string | null;
};

export type WaitTimePrediction = {
  estimated_minutes: number;
  lower_bound_minutes: number;
  upper_bound_minutes: number;
  confidence: number;
  model_version: string;
  factors: {
    people_ahead: number;
    queue_length: number;
    average_service_duration: number;
    active_counters: number;
    historical_samples: number;
    service_type: string;
    hour_of_day: number;
    day_of_week: number;
    current_processing_rate: number;
    explanation: string;
  };
};

export type QueueHistoryResponse = {
  page: number;
  page_size: number;
  total: number;
  items: {
    entry_id: string;
    queue_id: string;
    queue_name: string;
    queue_prefix: string;
    queue_number: number;
    status: QueueEntryStatus;
    joined_at: string;
    completed_at: string | null;
  }[];
};

export type AdminAnalytics = {
  customers_served_today: number;
  customers_waiting: number;
  average_waiting_time: number;
  average_service_time: number;
  completion_rate: number;
  skip_rate: number;
  cancellation_rate: number;
  busiest_service: { name: string; count: number } | null;
  busiest_hour: { hour: number; count: number } | null;
};
