import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PageContainer } from "../components/common/PageContainer";
import { WS_BASE, apiRequest } from "../services/api";
import { startWebSocketHeartbeat } from "../utils/websocketHeartbeat";
import {
  assignFeedback,
  addFeedbackNote,
  createImprovementTask,
  confirmFeedbackResolution,
  exportFeedback,
  getFeedbackMetrics,
  getFeedbackBranches,
  getFeatureRequests,
  getManagedFeedback,
  getMyFeedback,
  getFeedbackReviewers,
  getImprovementTasks,
  replyToFeedback,
  removeFeatureVote,
  voteForFeature,
  updateFeedbackStatus,
  updateFeedbackPriority,
  updateImprovementTask,
  type FeedbackCategory,
  type FeedbackImprovementTaskUpdate,
  type FeedbackReport,
  type FeedbackStatus,
} from "../services/feedback";
import { useAuthStore } from "../store/authStore";

const categories: FeedbackCategory[] = [
  "general",
  "bug",
  "feature_request",
  "ui_accessibility",
  "queue_accuracy",
  "performance_connection",
  "security_privacy",
  "account_login",
  "staff_service",
  "organization_setup_migration",
  "notification",
  "other",
];

const statuses: FeedbackStatus[] = [
  "new",
  "under_review",
  "planned",
  "in_progress",
  "waiting_for_information",
  "resolved",
  "declined",
  "duplicate",
];
const taskTransitions: Record<string, string[]> = {
  reviewed: ["prioritized", "declined"],
  prioritized: ["assigned", "declined"],
  assigned: ["implemented", "declined"],
  implemented: ["tested"],
  tested: ["released", "implemented"],
  released: ["measured"],
  measured: [],
  declined: ["reviewed"],
};

function useFeedbackUpdates(enabled: boolean) {
  const client = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stopHeartbeat = () => {};

    const connect = async () => {
      try {
        const result = await apiRequest<{ ticket: string }>("/api/v1/feedback/ws-ticket", {
          method: "POST",
        });
        if (stopped) return;
        socket = new WebSocket(
          `${WS_BASE}/ws/feedback?${new URLSearchParams({ ticket: result.ticket })}`,
        );
        const activeSocket = socket;
        socket.onopen = () => {
          stopHeartbeat();
          stopHeartbeat = startWebSocketHeartbeat(activeSocket);
          void client.invalidateQueries({ queryKey: ["feedback-managed"] });
          void client.invalidateQueries({ queryKey: ["feedback-mine"] });
        };
        socket.onmessage = () => {
          void client.invalidateQueries({ queryKey: ["feedback-managed"] });
          void client.invalidateQueries({ queryKey: ["feedback-mine"] });
          void client.invalidateQueries({ queryKey: ["feedback-metrics"] });
        };
        socket.onclose = () => {
          stopHeartbeat();
          stopHeartbeat = () => {};
          if (!stopped) retry = setTimeout(() => void connect(), 1500);
        };
      } catch {
        if (!stopped) retry = setTimeout(() => void connect(), 5000);
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (retry) clearTimeout(retry);
      stopHeartbeat();
      socket?.close();
    };
  }, [client, enabled]);
}

function label(value: string): string {
  return value.replaceAll("_", " ");
}

export function FeedbackCenterPage() {
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  const client = useQueryClient();
  const isManaged =
    (user?.role === "admin" || user?.role === "super_admin") &&
    !location.pathname.endsWith("/history");
  const [selectedId, setSelectedId] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [branchFilter, setBranchFilter] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "priority" | "votes">("newest");
  const [page, setPage] = useState(1);
  const [reply, setReply] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [resolution, setResolution] = useState("");
  const [release, setRelease] = useState("");
  const [message, setMessage] = useState("");
  const [taskEdits, setTaskEdits] = useState<
    Record<string, FeedbackImprovementTaskUpdate>
  >({});
  useFeedbackUpdates(isManaged || Boolean(user));

  const mine = useQuery({
    queryKey: ["feedback-mine"],
    queryFn: () => getMyFeedback(page),
    enabled: !isManaged,
    placeholderData: (previous) => previous,
  });
  const managed = useQuery({
    queryKey: [
      "feedback-managed",
      categoryFilter,
      statusFilter,
      branchFilter,
      sortBy,
      search,
      page,
    ],
    queryFn: () =>
      getManagedFeedback({
        page,
        category: categoryFilter ? (categoryFilter as FeedbackCategory) : undefined,
        status: statusFilter ? (statusFilter as FeedbackStatus) : undefined,
        branch_id: branchFilter || undefined,
        sort_by: sortBy,
        search: search.trim() || undefined,
      }),
    enabled: isManaged,
    placeholderData: (previous) => previous,
    refetchInterval: 30_000,
  });
  const metrics = useQuery({
    queryKey: ["feedback-metrics"],
    queryFn: getFeedbackMetrics,
    enabled: isManaged,
    refetchInterval: 60_000,
  });
  const features = useQuery({
    queryKey: ["feedback-features"],
    queryFn: () => getFeatureRequests(),
    enabled: !isManaged,
  });
  const reviewers = useQuery({
    queryKey: ["feedback-reviewers"],
    queryFn: getFeedbackReviewers,
    enabled: isManaged,
  });
  const branches = useQuery({
    queryKey: ["feedback-branches"],
    queryFn: getFeedbackBranches,
    enabled: isManaged,
  });
  const tasks = useQuery({
    queryKey: ["feedback-improvement-tasks"],
    queryFn: getImprovementTasks,
    enabled: isManaged,
  });
  const reports = useMemo(
    () => (isManaged ? managed.data?.items ?? [] : mine.data?.items ?? []),
    [isManaged, managed.data?.items, mine.data?.items],
  );
  const totalReports = isManaged
    ? (managed.data?.total ?? 0)
    : (mine.data?.total ?? 0);
  const totalPages = Math.max(1, Math.ceil(totalReports / 20));
  const selected = useMemo(
    () => reports.find((report) => report.id === selectedId) ?? reports[0],
    [reports, selectedId],
  );

  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["feedback-managed"] }),
      client.invalidateQueries({ queryKey: ["feedback-mine"] }),
      client.invalidateQueries({ queryKey: ["feedback-metrics"] }),
      client.invalidateQueries({ queryKey: ["feedback-features"] }),
      client.invalidateQueries({ queryKey: ["feedback-reviewers"] }),
      client.invalidateQueries({ queryKey: ["feedback-branches"] }),
      client.invalidateQueries({ queryKey: ["feedback-improvement-tasks"] }),
    ]);
  };
  const statusMutation = useMutation({
    mutationFn: ({ report, next }: { report: FeedbackReport; next: FeedbackStatus }) =>
      updateFeedbackStatus(report.id, {
        status: next,
        resolution_summary: next === "resolved" ? resolution : undefined,
        release_version: next === "resolved" ? release || undefined : undefined,
      }),
    onSuccess: async () => {
      setMessage("Feedback status updated.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const replyMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => replyToFeedback(id, body),
    onSuccess: async () => {
      setReply("");
      setMessage("Your response was sent.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const noteMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => addFeedbackNote(id, body),
    onSuccess: async () => {
      setInternalNote("");
      setMessage("Internal note saved.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const confirmationMutation = useMutation({
    mutationFn: ({ id, helpful }: { id: string; helpful: boolean }) =>
      confirmFeedbackResolution(id, helpful),
    onSuccess: async () => {
      setMessage("Thank you for confirming the outcome.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const assignmentMutation = useMutation({
    mutationFn: ({ id, assignedTo }: { id: string; assignedTo: string | null }) =>
      assignFeedback(id, assignedTo),
    onSuccess: async () => {
      setMessage("Feedback assignment updated.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const priorityMutation = useMutation({
    mutationFn: ({
      id,
      priority,
      severity,
    }: {
      id: string;
      priority: number;
      severity: FeedbackReport["severity"];
    }) => updateFeedbackPriority(id, priority, severity),
    onSuccess: async () => {
      setMessage("Feedback priority updated.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const taskCreateMutation = useMutation({
    mutationFn: (report: FeedbackReport) =>
      createImprovementTask(report.id, {
        title: report.title,
        description: report.description,
        priority: report.priority,
        impact: report.severity,
      }),
    onSuccess: async () => {
      setMessage("Product improvement task created and linked to this report.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const taskUpdateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: FeedbackImprovementTaskUpdate;
    }) => updateImprovementTask(id, payload),
    onSuccess: async () => {
      setMessage("Product improvement task updated.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });
  const voteMutation = useMutation({
    mutationFn: ({ id, voted }: { id: string; voted: boolean }) =>
      voted ? removeFeatureVote(id) : voteForFeature(id),
    onSuccess: async () => {
      setMessage("Feature request vote updated.");
      await refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });

  async function downloadExport() {
    try {
      const blob = await exportFeedback();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "feedback.csv";
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Feedback export downloaded.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    }
  }

  const loading = isManaged ? managed.isLoading : mine.isLoading;
  const error = isManaged ? managed.error : mine.error;
  const retry = isManaged ? managed.refetch : mine.refetch;
  const breakdowns: [string, Record<string, number>][] = metrics.data
    ? [
        ["By severity", metrics.data.by_severity],
        ["By application area", metrics.data.by_application_area],
        ["By organization", metrics.data.by_organization],
        ["By branch", metrics.data.by_branch],
        ["By role", metrics.data.by_role],
      ]
    : [];

  return (
    <PageContainer className="py-8 sm:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">
            {isManaged ? "Product insights" : "Your reports"}
          </p>
          <h1 className="mt-1 text-3xl font-black sm:text-4xl">
            {isManaged ? "Feedback center" : "Feedback history"}
          </h1>
        </div>
        <div className="flex flex-wrap gap-3">
          {!isManaged && (
            <Link className="rounded-full bg-ink px-5 py-3 text-sm font-bold text-white" to="/">
              Send feedback
            </Link>
          )}
          {isManaged && (
            <button
              type="button"
              onClick={() => void downloadExport()}
              className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold"
            >
              Export CSV
            </button>
          )}
        </div>
      </div>

      {isManaged && metrics.data && (
        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7" aria-label="Feedback metrics">
          {[
            ["Reports", metrics.data.total],
            ["New", metrics.data.new],
            ["Unresolved", metrics.data.unresolved],
            ["Average rating", metrics.data.average_rating ?? "No ratings"],
            [
              "Confirmed solved",
              metrics.data.resolution_confirmation_rate === null
                ? "No confirmations"
                : `${metrics.data.resolution_confirmation_rate}%`,
            ],
            [
              "Avg. first review",
              metrics.data.average_time_to_first_review_hours === null
                ? "No reviews"
                : `${metrics.data.average_time_to_first_review_hours}h`,
            ],
            [
              "Avg. resolution",
              metrics.data.average_resolution_time_hours === null
                ? "No resolutions"
                : `${metrics.data.average_resolution_time_hours}h`,
            ],
          ].map(([name, value]) => (
            <div key={name} className="rounded-2xl border border-ink/10 bg-white p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-ink/60">{name}</p>
              <p className="mt-1 text-2xl font-black">{value}</p>
            </div>
          ))}
        </section>
      )}

      {!isManaged && features.data && features.data.items.length > 0 && (
        <section className="mt-6" aria-labelledby="feature-requests-heading">
          <h2 id="feature-requests-heading" className="text-2xl font-black">
            Feature requests under consideration
          </h2>
          <p className="mt-1 text-sm text-ink/60">
            These requests have been reviewed. Votes help prioritize discussion, but do not
            guarantee implementation.
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {features.data.items.map((feature) => (
              <article key={feature.id} className="rounded-2xl border border-ink/10 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold">{feature.title}</h3>
                    <p className="mt-1 text-sm text-ink/70">{feature.description}</p>
                    <p className="mt-2 text-xs text-ink/55">
                      {label(feature.status)} · {feature.votes} vote(s)
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={voteMutation.isPending}
                    onClick={() =>
                      voteMutation.mutate({
                        id: feature.id,
                        voted: feature.voted_by_current_user,
                      })
                    }
                    className="shrink-0 rounded-full border border-emerald-800 px-3 py-2 text-xs font-bold text-emerald-900 disabled:opacity-50"
                  >
                    {feature.voted_by_current_user ? "Remove vote" : "Vote"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {isManaged && (
        <section className="mt-6 flex flex-wrap gap-3 rounded-2xl bg-white p-4" aria-label="Filter feedback">
          <label className="text-sm font-semibold">
            Category
            <select
              value={categoryFilter}
              onChange={(event) => {
                setCategoryFilter(event.target.value);
                setPage(1);
              }}
              className="ml-2 rounded-lg border border-ink/20 bg-white px-2 py-1.5"
            >
              <option value="">All categories</option>
              {categories.map((item) => <option key={item} value={item}>{label(item)}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">
            Status
            <select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
              className="ml-2 rounded-lg border border-ink/20 bg-white px-2 py-1.5"
            >
              <option value="">All statuses</option>
              {statuses.map((item) => <option key={item} value={item}>{label(item)}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">
            Branch
            <select
              value={branchFilter}
              onChange={(event) => {
                setBranchFilter(event.target.value);
                setPage(1);
              }}
              className="ml-2 rounded-lg border border-ink/20 bg-white px-2 py-1.5"
            >
              <option value="">All branches</option>
              {(branches.data ?? []).map((branch) => (
                <option key={branch.id} value={branch.id}>{branch.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold">
            Sort
            <select
              value={sortBy}
              onChange={(event) => {
                setSortBy(event.target.value as typeof sortBy);
                setPage(1);
              }}
              className="ml-2 rounded-lg border border-ink/20 bg-white px-2 py-1.5"
            >
              <option value="newest">Newest</option>
              <option value="priority">Priority</option>
              <option value="votes">Feature request votes</option>
            </select>
          </label>
          <label className="min-w-52 flex-1 text-sm font-semibold">
            Search
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              maxLength={100}
              className="ml-2 w-full rounded-lg border border-ink/20 px-2 py-1.5"
              placeholder="Title or report text"
            />
          </label>
        </section>
      )}
      {isManaged && metrics.data && (
        <section className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4" aria-label="Feedback breakdowns">
          {breakdowns.map(([heading, breakdown]) => (
            <div key={String(heading)} className="rounded-2xl border border-ink/10 bg-white p-4">
              <h2 className="text-sm font-bold">{heading}</h2>
              <ul className="mt-2 space-y-1 text-xs text-ink/70">
                {Object.entries(breakdown).length === 0 ? (
                  <li>No data</li>
                ) : (
                  Object.entries(breakdown)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 5)
                    .map(([key, count]) => (
                      <li key={key} className="flex justify-between gap-2">
                        <span className="break-all">{label(key)}</span>
                        <span className="font-bold">{count}</span>
                      </li>
                    ))
                )}
              </ul>
            </div>
          ))}
        </section>
      )}

      {loading && <div className="mt-6"><LoadingState label="Loading feedback..." /></div>}
      {error instanceof Error && (
        <div className="mt-6">
          <ErrorState message={error.message} onRetry={() => void retry()} />
        </div>
      )}
      {message && (
        <p
          className={`mt-4 text-sm ${/updated|sent|saved|confirming|downloaded/i.test(message) ? "text-emerald-900" : "text-red-800"}`}
          role={/updated|sent|saved|confirming|downloaded/i.test(message) ? "status" : "alert"}
        >
          {message}
        </p>
      )}
      {!loading && !error && reports.length === 0 && (
        <div className="mt-6 rounded-2xl border border-ink/10 bg-white p-6">
          <p className="font-bold">No feedback reports found.</p>
          <p className="mt-1 text-sm text-ink/60">
            {isManaged
              ? "New submissions will appear here after they are stored by the backend."
              : "Reports you submit while signed in will be listed here."}
          </p>
        </div>
      )}

      {!loading && reports.length > 0 && (
        <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(16rem,0.8fr)_minmax(0,1.2fr)]">
          <section aria-label="Feedback reports" className="space-y-3">
            {reports.map((report) => (
              <button
                key={report.id}
                type="button"
                onClick={() => setSelectedId(report.id)}
                className={`w-full rounded-2xl border bg-white p-4 text-left ${
                  selected?.id === report.id
                    ? "border-emerald-800 ring-1 ring-emerald-800"
                    : "border-ink/10 hover:border-ink/30"
                }`}
              >
                <span className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold">{report.title}</span>
                  <span className="rounded-full bg-ink/5 px-2.5 py-1 text-xs font-semibold">
                    {label(report.status)}
                  </span>
                </span>
                <span className="mt-2 block text-xs text-ink/60">
                  {label(report.category)} · {new Date(report.created_at).toLocaleString()}
                </span>
              </button>
            ))}
          </section>
          {selected && (
            <article className="rounded-2xl border border-ink/10 bg-white p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-emerald-800">
                    {label(selected.category)} · {selected.severity} · priority {selected.priority}
                  </p>
                  <h2 className="mt-1 text-2xl font-black">{selected.title}</h2>
                </div>
                <p className="max-w-full break-all font-mono text-xs text-ink/55">{selected.id}</p>
              </div>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-6">{selected.description}</p>
              {selected.improvement_suggestion && (
                <p className="mt-3 rounded-xl bg-ink/5 p-3 text-sm">
                  <strong>Suggested improvement:</strong> {selected.improvement_suggestion}
                </p>
              )}
              <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                <div><dt className="inline font-semibold">Submitted: </dt><dd className="inline">{new Date(selected.created_at).toLocaleString()}</dd></div>
                <div><dt className="inline font-semibold">Page: </dt><dd className="inline">{selected.page_identifier ?? "Not provided"}</dd></div>
                <div><dt className="inline font-semibold">App version: </dt><dd className="inline">{selected.app_version ?? "Not provided"}</dd></div>
                <div><dt className="inline font-semibold">Rating: </dt><dd className="inline">{selected.rating ?? "Not rated"}</dd></div>
              </dl>
              {selected.resolution_summary && (
                <div className="mt-4 rounded-xl bg-emerald-50 p-4">
                  <p className="font-bold">Resolution</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{selected.resolution_summary}</p>
                  {selected.release_version && <p className="mt-1 text-xs">Release {selected.release_version}</p>}
                </div>
              )}
              {!loading && !error && (
                <nav className="mt-5 flex items-center justify-end gap-3" aria-label="Feedback pages">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => current - 1)}
                    className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-sm">
                    Page {page} of{" "}
                    {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={
                      page >=
                      totalPages
                    }
                    onClick={() => setPage((current) => current + 1)}
                    className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold disabled:opacity-40"
                  >
                    Next
                  </button>
                </nav>
              )}
              <section className="mt-5 border-t border-ink/10 pt-4">
                <h3 className="font-bold">Responses and status history</h3>
                {selected.replies.length ? (
                  <ul className="mt-3 space-y-2">
                    {selected.replies.map((item) => (
                      <li key={item.id} className="rounded-xl bg-ink/5 p-3">
                        {item.is_internal && isManaged && (
                          <p className="text-xs font-bold uppercase text-amber-900">Internal note</p>
                        )}
                        <p className="whitespace-pre-wrap text-sm">{item.body}</p>
                        <p className="mt-1 text-xs text-ink/55">{new Date(item.created_at).toLocaleString()}</p>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-2 text-sm text-ink/60">No responses yet.</p>}
                <ol className="mt-3 flex flex-wrap gap-2" aria-label="Status history">
                  {selected.status_history.map((item, index) => (
                    <li key={`${item.created_at}-${index}`} className="rounded-full bg-ink/5 px-3 py-1 text-xs">
                      {label(item.new_status)} · {new Date(item.created_at).toLocaleDateString()}
                    </li>
                  ))}
                </ol>
              </section>

              {isManaged ? (
                <div className="mt-5 space-y-4 border-t border-ink/10 pt-4">
                  <label className="block text-sm font-semibold">
                    Change status
                    <select
                      value={selected.status}
                      onChange={(event) =>
                        statusMutation.mutate({
                          report: selected,
                          next: event.target.value as FeedbackStatus,
                        })
                      }
                      disabled={statusMutation.isPending}
                      className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2"
                    >
                      {statuses.map((item) => <option key={item} value={item}>{label(item)}</option>)}
                    </select>
                  </label>
                  {selected.status !== "resolved" && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="text-sm font-semibold">
                        Resolution summary (required to resolve)
                        <input value={resolution} onChange={(event) => setResolution(event.target.value)} maxLength={3000} className="mt-1 block w-full rounded-xl border border-ink/20 px-3 py-2" />
                      </label>
                      <label className="text-sm font-semibold">
                        Release version (optional)
                        <input value={release} onChange={(event) => setRelease(event.target.value)} maxLength={40} className="mt-1 block w-full rounded-xl border border-ink/20 px-3 py-2" />
                      </label>
                    </div>
                  )}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm font-semibold">
                      Assigned reviewer
                      <select
                        value={selected.assigned_to_user_id ?? ""}
                        onChange={(event) =>
                          assignmentMutation.mutate({
                            id: selected.id,
                            assignedTo: event.target.value || null,
                          })
                        }
                        className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2"
                      >
                        <option value="">Unassigned</option>
                        {(reviewers.data ?? []).map((reviewer) => (
                          <option key={reviewer.id} value={reviewer.id}>
                            {reviewer.full_name} ({label(reviewer.role)})
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-sm font-semibold">
                        Priority
                        <select
                          value={selected.priority}
                          onChange={(event) =>
                            priorityMutation.mutate({
                              id: selected.id,
                              priority: Number(event.target.value),
                              severity: selected.severity,
                            })
                          }
                          className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2"
                        >
                          {[1, 2, 3, 4, 5].map((item) => (
                            <option key={item} value={item}>{item}</option>
                          ))}
                        </select>
                      </label>
                      <label className="text-sm font-semibold">
                        Severity
                        <select
                          value={selected.severity}
                          onChange={(event) =>
                            priorityMutation.mutate({
                              id: selected.id,
                              priority: selected.priority,
                              severity: event.target.value as FeedbackReport["severity"],
                            })
                          }
                          className="mt-1 block w-full rounded-xl border border-ink/20 bg-white px-3 py-2"
                        >
                          {(["low", "medium", "high", "critical"] as const).map((item) => (
                            <option key={item} value={item}>{item}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={
                      tasks.isLoading ||
                      (tasks.data ?? []).some((task) =>
                        task.feedback_report_ids.includes(selected.id),
                      ) ||
                      taskCreateMutation.isPending
                    }
                    onClick={() => taskCreateMutation.mutate(selected)}
                    className="rounded-full border border-emerald-800 px-4 py-2 text-sm font-bold text-emerald-900 disabled:opacity-50"
                  >
                    {(tasks.data ?? []).some((task) =>
                      task.feedback_report_ids.includes(selected.id),
                    )
                      ? "Improvement task linked"
                      : "Create improvement task"}
                  </button>
                  <form
                    className="space-y-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (reply.trim()) replyMutation.mutate({ id: selected.id, body: reply.trim() });
                    }}
                  >
                    <label className="block text-sm font-semibold" htmlFor="feedback-public-reply">Public reply</label>
                    <textarea id="feedback-public-reply" value={reply} onChange={(event) => setReply(event.target.value)} maxLength={5000} rows={2} className="w-full rounded-xl border border-ink/20 px-3 py-2" />
                    <button disabled={replyMutation.isPending || !reply.trim()} className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white">Send public reply</button>
                  </form>
                  <form
                    className="space-y-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (internalNote.trim()) noteMutation.mutate({ id: selected.id, body: internalNote.trim() });
                    }}
                  >
                    <label className="block text-sm font-semibold" htmlFor="feedback-internal-note">Internal note (reviewers only)</label>
                    <textarea id="feedback-internal-note" value={internalNote} onChange={(event) => setInternalNote(event.target.value)} maxLength={5000} rows={2} className="w-full rounded-xl border border-ink/20 px-3 py-2" />
                    <button disabled={noteMutation.isPending || !internalNote.trim()} className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold">Save internal note</button>
                  </form>
                </div>
              ) : (
                <>
                  {selected.status === "resolved" && selected.resolution_helpful === null && (
                    <div className="mt-4 rounded-xl bg-emerald-50 p-4">
                      <p className="font-semibold">Did this resolution solve your problem?</p>
                      <div className="mt-2 flex gap-2">
                        <button onClick={() => confirmationMutation.mutate({ id: selected.id, helpful: true })} className="rounded-full bg-emerald-900 px-4 py-2 text-sm font-bold text-white">Yes</button>
                        <button onClick={() => confirmationMutation.mutate({ id: selected.id, helpful: false })} className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold">No</button>
                      </div>
                    </div>
                  )}
                  <form
                    className="mt-4 space-y-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (reply.trim()) replyMutation.mutate({ id: selected.id, body: reply.trim() });
                    }}
                  >
                    <label className="block text-sm font-semibold" htmlFor="feedback-followup">Add a response</label>
                    <textarea id="feedback-followup" value={reply} onChange={(event) => setReply(event.target.value)} maxLength={5000} rows={2} className="w-full rounded-xl border border-ink/20 px-3 py-2" />
                    <button disabled={replyMutation.isPending || !reply.trim()} className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white">Send response</button>
                  </form>
                </>
              )}
            </article>
          )}
        </div>
      )}
      {isManaged && (tasks.data?.length ?? 0) > 0 && (
        <section className="mt-8" aria-labelledby="improvement-board-heading">
          <h2 id="improvement-board-heading" className="text-2xl font-black">
            Product improvement board
          </h2>
          <p className="mt-1 text-sm text-ink/60">
            Feedback remains separate from implementation; tasks move through human review,
            testing, release, and outcome measurement.
          </p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {tasks.data?.map((task) => (
              <article key={task.id} className="rounded-2xl border border-ink/10 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold">{task.title}</h3>
                    <p className="mt-1 text-xs text-ink/60">
                      Priority {task.priority} · {task.impact} impact ·{" "}
                      {task.feedback_report_ids.length} linked report(s)
                    </p>
                  </div>
                  <label className="text-xs font-semibold">
                    Status
                    <select
                      value={task.status}
                      onChange={(event) =>
                        taskUpdateMutation.mutate({
                          id: task.id,
                          payload: {
                            status: event.target.value,
                            acceptance_criteria:
                              taskEdits[task.id]?.acceptance_criteria ??
                              task.acceptance_criteria,
                            target_release:
                              taskEdits[task.id]?.target_release ?? task.target_release,
                            release_version:
                              taskEdits[task.id]?.release_version ?? task.release_version,
                            verification_notes:
                              taskEdits[task.id]?.verification_notes ??
                              task.verification_notes,
                            post_release_outcome:
                              taskEdits[task.id]?.post_release_outcome ??
                              task.post_release_outcome,
                          },
                        })
                      }
                      className="ml-2 rounded-lg border border-ink/20 bg-white px-2 py-1"
                    >
                      <option value={task.status}>{label(task.status)}</option>
                      {(taskTransitions[task.status] ?? []).map((nextStatus) => (
                        <option key={nextStatus} value={nextStatus}>{label(nextStatus)}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm">{task.description}</p>
                {task.acceptance_criteria && (
                  <p className="mt-2 text-sm"><strong>Acceptance criteria:</strong> {task.acceptance_criteria}</p>
                )}
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="text-xs font-semibold">
                    Owner
                    <select
                      value={task.assigned_to_user_id ?? ""}
                      onChange={(event) =>
                        taskUpdateMutation.mutate({
                          id: task.id,
                          payload: { assigned_to_user_id: event.target.value || null },
                        })
                      }
                      className="mt-1 block w-full rounded-lg border border-ink/20 bg-white px-2 py-1.5"
                    >
                      <option value="">Unassigned</option>
                      {(reviewers.data ?? []).map((reviewer) => (
                        <option key={reviewer.id} value={reviewer.id}>
                          {reviewer.full_name} ({label(reviewer.role)})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs font-semibold">
                    Target release
                    <input
                      value={taskEdits[task.id]?.target_release ?? task.target_release ?? ""}
                      onChange={(event) =>
                        setTaskEdits((current) => ({
                          ...current,
                          [task.id]: {
                            ...current[task.id],
                            target_release: event.target.value,
                          },
                        }))
                      }
                      maxLength={40}
                      className="mt-1 block w-full rounded-lg border border-ink/20 px-2 py-1.5"
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Acceptance criteria
                    <textarea
                      value={
                        taskEdits[task.id]?.acceptance_criteria ??
                        task.acceptance_criteria ??
                        ""
                      }
                      onChange={(event) =>
                        setTaskEdits((current) => ({
                          ...current,
                          [task.id]: {
                            ...current[task.id],
                            acceptance_criteria: event.target.value,
                          },
                        }))
                      }
                      maxLength={3000}
                      rows={2}
                      className="mt-1 block w-full rounded-lg border border-ink/20 px-2 py-1.5"
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Release version
                    <input
                      value={taskEdits[task.id]?.release_version ?? task.release_version ?? ""}
                      onChange={(event) =>
                        setTaskEdits((current) => ({
                          ...current,
                          [task.id]: {
                            ...current[task.id],
                            release_version: event.target.value,
                          },
                        }))
                      }
                      maxLength={40}
                      className="mt-1 block w-full rounded-lg border border-ink/20 px-2 py-1.5"
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Test evidence
                    <textarea
                      value={
                        taskEdits[task.id]?.verification_notes ??
                        task.verification_notes ??
                        ""
                      }
                      onChange={(event) =>
                        setTaskEdits((current) => ({
                          ...current,
                          [task.id]: {
                            ...current[task.id],
                            verification_notes: event.target.value,
                          },
                        }))
                      }
                      maxLength={3000}
                      rows={2}
                      className="mt-1 block w-full rounded-lg border border-ink/20 px-2 py-1.5"
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Post-release outcome
                    <textarea
                      value={
                        taskEdits[task.id]?.post_release_outcome ??
                        task.post_release_outcome ??
                        ""
                      }
                      onChange={(event) =>
                        setTaskEdits((current) => ({
                          ...current,
                          [task.id]: {
                            ...current[task.id],
                            post_release_outcome: event.target.value,
                          },
                        }))
                      }
                      maxLength={3000}
                      rows={2}
                      className="mt-1 block w-full rounded-lg border border-ink/20 px-2 py-1.5"
                    />
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    taskUpdateMutation.mutate({
                      id: task.id,
                      payload: {
                        acceptance_criteria:
                          taskEdits[task.id]?.acceptance_criteria ??
                          task.acceptance_criteria,
                        target_release:
                          taskEdits[task.id]?.target_release ?? task.target_release,
                        release_version:
                          taskEdits[task.id]?.release_version ?? task.release_version,
                        verification_notes:
                          taskEdits[task.id]?.verification_notes ??
                          task.verification_notes,
                        post_release_outcome:
                          taskEdits[task.id]?.post_release_outcome ??
                          task.post_release_outcome,
                      },
                    })
                  }
                  disabled={taskUpdateMutation.isPending}
                  className="mt-3 rounded-full border border-ink/20 px-4 py-2 text-xs font-bold"
                >
                  Save task details
                </button>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-ink/60">
                  {task.target_release && <span>Target: {task.target_release}</span>}
                  {task.release_version && <span>Released: {task.release_version}</span>}
                  {task.verification_notes && <span>Tested: {task.verification_notes}</span>}
                  {task.post_release_outcome && <span>Outcome: {task.post_release_outcome}</span>}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </PageContainer>
  );
}
