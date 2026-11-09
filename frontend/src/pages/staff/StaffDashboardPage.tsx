import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { QueueRequestReviewPanel } from "../../components/queue/QueueRequestReviewPanel";
import { ErrorState } from "../../components/common/ErrorState";
import { AnnouncementFeed } from "../../components/common/AnnouncementFeed";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  CurrentCustomerCard,
  QueueStatusBadge,
  StatsCard,
} from "../../components/staff/StaffCards";
import { CounterSelector } from "../../components/staff/CounterSelector";
import { StaffQueueTable } from "../../components/staff/StaffQueueTable";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import {
  getStaffDashboard,
  getStaffCustomers,
  getStaffHistory,
  getStaffQueue,
  nextCustomer,
  setStaffEntryPriority,
  setQueueStatus,
  staffAction,
  transferStaffQueueEntry,
} from "../../services/staff";
import { useAuthStore } from "../../store/authStore";
import type { QueuePosition } from "../../types/api";
import { formatQueueNumber } from "../../utils/queueNumber";

type StaffQueueAction = "call" | "start" | "complete" | "skip";

export function StaffDashboardPage() {
  const token = useAuthStore((state) => state.token)!;
  const client = useQueryClient();
  const location = useLocation();
  const customerView = location.pathname.endsWith("/customers");
  const historyView = location.pathname.endsWith("/history");
  const [selectedCounterId, setSelectedCounterId] = useState("");
  const [selectedQueueId, setSelectedQueueId] = useState("");
  const dashboard = useQuery({
    queryKey: ["staff-dashboard"],
    queryFn: () => getStaffDashboard(token),
    refetchInterval: 30_000,
  });
  const customers = useQuery({
    queryKey: ["staff-customers"],
    queryFn: () => getStaffCustomers(token),
    enabled: customerView,
    refetchInterval: 30_000,
  });
  const history = useQuery({
    queryKey: ["staff-history"],
    queryFn: () => getStaffHistory(token),
    enabled: historyView,
    refetchInterval: 30_000,
  });

  const queues = dashboard.data?.queues ?? [];
  const availableCounters =
    dashboard.data?.counters.filter((counter) => counter.status === "available") ?? [];
  const summary =
    queues.find((queue) => queue.id === selectedQueueId) ?? queues[0];
  const counterId =
    availableCounters.find((counter) => counter.id === selectedCounterId)?.id ??
    availableCounters[0]?.id ??
    "";
  const queueId = summary?.id;
  const connection = useQueueWebSocket(
    customerView || historyView ? undefined : queueId,
    token,
  );
  const queue = useQuery({
    queryKey: ["staff-queue", queueId],
    queryFn: () => getStaffQueue(queueId!, token),
    enabled: Boolean(queueId),
    refetchInterval: connection.status === "connected" ? 30_000 : 5_000,
  });

  const refreshQueue = () => {
    void client.invalidateQueries({ queryKey: ["staff-dashboard"] });
    void client.invalidateQueries({ queryKey: ["staff-queue", queueId] });
  };
  const action = useMutation({
    mutationFn: ({
      entry,
      name,
    }: {
      entry: QueuePosition;
      name: StaffQueueAction;
    }) =>
      staffAction(
        entry.id,
        name,
        token,
        name === "call" || name === "start" ? counterId : undefined,
      ),
    onSuccess: refreshQueue,
  });
  const next = useMutation({
    mutationFn: () => nextCustomer(queueId!, token, counterId),
    onSuccess: refreshQueue,
  });
  const priority = useMutation({
    mutationFn: ({
      entry,
      value,
    }: {
      entry: QueuePosition;
      value: number;
    }) => setStaffEntryPriority(entry.id, value, token),
    onSuccess: refreshQueue,
  });
  const transfer = useMutation({
    mutationFn: ({
      entry,
      targetQueueId,
    }: {
      entry: QueuePosition;
      targetQueueId: string;
    }) => transferStaffQueueEntry(entry.id, targetQueueId, token),
    onSuccess: refreshQueue,
  });
  const status = useMutation({
    mutationFn: (value: "pause" | "resume") =>
      setQueueStatus(queueId!, value, token),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ["staff-dashboard"] }),
  });

  if (!customerView && !historyView && dashboard.isLoading) return <LoadingState />;
  if (!customerView && !historyView && !dashboard.data) {
    return (
      <ErrorState
        message="Unable to load the staff dashboard."
        onRetry={() => void dashboard.refetch()}
      />
    );
  }

  const entries = queue.data?.entries ?? [];
  const waitingEntry = entries.find((entry) => entry.status === "waiting");
  const currentEntry = entries.find(
    (entry) => entry.status === "serving" || entry.status === "called",
  );
  const mutationError =
    action.error ?? next.error ?? status.error ?? priority.error ?? transfer.error;

  if (customerView) {
    return (
      <PageContainer className="py-10">
        <AnnouncementFeed />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-ink/60">{dashboard.data?.branch?.name}</p>
            <h1 className="text-4xl font-black">Customers</h1>
            <p className="mt-2 text-sm text-ink/60">
              Recent customer activity across your assigned branch.
            </p>
          </div>
          <Link className="font-semibold text-emerald-800 underline" to="/staff/dashboard">
            Back to dashboard
          </Link>
        </div>
        {customers.isLoading && <LoadingState label="Loading branch customers..." />}
        {customers.isError && (
          <div className="mt-6">
            <ErrorState
              message="Unable to load branch customers."
              onRetry={() => void customers.refetch()}
            />
          </div>
        )}
        {customers.data && (
          <div className="mt-6 overflow-x-auto rounded-2xl bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-ink/5">
                <tr>
                  <th className="p-4">Customer</th>
                  <th className="p-4">Queue</th>
                  <th className="p-4">Ticket</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Joined</th>
                </tr>
              </thead>
              <tbody>
                {customers.data.map((item) => (
                  <tr className="border-t border-ink/10" key={item.entry_id}>
                    <td className="p-4">
                      <span className="block font-semibold">{item.customer.full_name}</span>
                      <span className="text-ink/60">{item.customer.email}</span>
                    </td>
                    <td className="p-4">{item.queue_name}</td>
                    <td className="p-4 font-bold">
                      {formatQueueNumber(item.queue_prefix, item.queue_number)}
                    </td>
                    <td className="p-4 capitalize">{item.status}</td>
                    <td className="p-4">{new Date(item.joined_at).toLocaleString()}</td>
                  </tr>
                ))}
                {customers.data.length === 0 && (
                  <tr>
                    <td className="p-6 text-center text-ink/60" colSpan={5}>
                      No customer activity at this branch yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </PageContainer>
    );
  }

  if (historyView) {
    return (
      <PageContainer className="py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-ink/60">{dashboard.data?.branch?.name}</p>
            <h1 className="text-4xl font-black">Queue history</h1>
            <p className="mt-2 text-sm text-ink/60">
              Recently completed and skipped services at your assigned branch.
            </p>
          </div>
          <Link className="font-semibold text-emerald-800 underline" to="/staff/dashboard">
            Back to dashboard
          </Link>
        </div>
        {history.isLoading && <LoadingState label="Loading queue history..." />}
        {history.isError && (
          <div className="mt-6">
            <ErrorState
              message="Unable to load queue history."
              onRetry={() => void history.refetch()}
            />
          </div>
        )}
        {history.data && (
          <div className="mt-6 overflow-x-auto rounded-2xl bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-ink/5">
                <tr>
                  <th className="p-4">Customer</th>
                  <th className="p-4">Queue</th>
                  <th className="p-4">Ticket</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Completed</th>
                </tr>
              </thead>
              <tbody>
                {history.data.map((item) => (
                  <tr className="border-t border-ink/10" key={item.entry_id}>
                    <td className="p-4">
                      <span className="block font-semibold">{item.customer.full_name}</span>
                      <span className="text-ink/60">{item.customer.email}</span>
                    </td>
                    <td className="p-4">{item.queue_name}</td>
                    <td className="p-4 font-bold">
                      {formatQueueNumber(item.queue_prefix, item.queue_number)}
                    </td>
                    <td className="p-4 capitalize">{item.status}</td>
                    <td className="p-4">
                      {item.completed_at
                        ? new Date(item.completed_at).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))}
                {history.data.length === 0 && (
                  <tr>
                    <td className="p-6 text-center text-ink/60" colSpan={5}>
                      No completed or skipped services have been recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </PageContainer>
    );
  }

  if (!dashboard.data) {
    return (
      <ErrorState
        message="Unable to load the staff dashboard."
        onRetry={() => void dashboard.refetch()}
      />
    );
  }

  return (
    <PageContainer className="py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink/60">{dashboard.data.branch?.name}</p>
          <h1 className="text-4xl font-black">Staff dashboard</h1>
          <p className="mt-1 text-xs text-ink/50" aria-live="polite">
            Updated {new Date(dashboard.dataUpdatedAt).toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {queueId && connection.status !== "connected" && (
            <span className="text-xs text-amber-700">
              Live updates: {connection.status}
            </span>
          )}
          {summary && <QueueStatusBadge status={summary.status} />}
        </div>
      </div>

      {dashboard.isError && (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">
          Live dashboard data could not refresh. Showing the last loaded data.{" "}
          <button
            className="ml-2 font-bold underline"
            onClick={() => void dashboard.refetch()}
          >
            Retry
          </button>
        </p>
      )}
      {queue.isError && (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">
          The live queue could not refresh.{" "}
          <button
            className="ml-2 font-bold underline"
            onClick={() => void queue.refetch()}
          >
            Retry
          </button>
        </p>
      )}
      {mutationError && (
        <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">
          {mutationError.message || "The queue action failed. Please try again."}
        </p>
      )}

      {queues.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-ink/10 bg-white p-6">
          <h2 className="text-xl font-black">No queues assigned</h2>
          <p className="mt-2 text-sm text-ink/60">
            There are no queues configured for your assigned branch yet.
          </p>
        </div>
      ) : (
        summary && (
          <>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-ink/10 bg-white p-5">
              <div>
                <h2 className="text-xl font-black">{summary.name}</h2>
                <p className="mt-1 text-sm text-ink/60">
                  Choose the queue to manage at this branch.
                </p>
              </div>
              {queues.length > 1 && (
                <label className="grid gap-1 text-sm font-semibold">
                  Queue
                  <select
                    aria-label="Queue"
                    className="min-w-48 rounded-lg border px-3 py-2"
                    value={summary.id}
                    onChange={(event) => setSelectedQueueId(event.target.value)}
                  >
                    {queues.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatsCard label="Waiting" value={summary.waiting_count} />
              <StatsCard label="Serving" value={summary.serving_count} />
              <StatsCard label="Completed" value={summary.completed_count} />
              <StatsCard label="Skipped" value={summary.skipped_count} />
            </div>

            {queue.isLoading && (
              <div className="mt-6">
                <LoadingState label="Loading queue..." />
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-ink/10 bg-white p-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-ink/50">
                  Next customer
                </p>
                <p className="mt-1 text-4xl font-black">
                  {waitingEntry
                    ? formatQueueNumber(
                        waitingEntry.queue_prefix,
                        waitingEntry.queue_number,
                      )
                    : queue.isLoading
                      ? "Loading..."
                      : "No waiting customers"}
                </p>
              </div>
              <CounterSelector
                counters={availableCounters}
                value={counterId}
                onChange={setSelectedCounterId}
              />
              <button
                className="rounded-full bg-ink px-6 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  !counterId ||
                  !waitingEntry ||
                  summary.status !== "open" ||
                  action.isPending
                }
                onClick={() => {
                  if (waitingEntry) action.mutate({ entry: waitingEntry, name: "call" });
                }}
              >
                CALL
              </button>
            </div>

            {availableCounters.length === 0 && (
              <p className="mt-3 text-sm text-amber-800">
                No counters are currently available. Set a counter to available
                before calling or starting a customer.
              </p>
            )}

            <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_2fr]">
              <CurrentCustomerCard
                number={currentEntry?.queue_number}
                prefix={currentEntry?.queue_prefix}
                status={currentEntry?.status}
              />
              <div className="rounded-2xl border border-ink/10 bg-white p-6">
                <h2 className="text-xl font-black">{summary.name}</h2>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => next.mutate()}
                    disabled={
                      !counterId ||
                      !waitingEntry ||
                      summary.status !== "open" ||
                      next.isPending
                    }
                  >
                    {next.isPending ? "Calling..." : "Next"}
                  </button>
                  <button
                    className="rounded-full border px-4 py-2 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() =>
                      status.mutate(summary.status === "paused" ? "resume" : "pause")
                    }
                    disabled={summary.status === "closed" || status.isPending}
                  >
                    {summary.status === "paused"
                      ? "Resume queue"
                      : summary.status === "closed"
                        ? "Queue closed"
                        : "Pause queue"}
                  </button>
                </div>
              </div>
            </div>

            {queue.data && (
              <div className="mt-8">
                <StaffQueueTable
                  entries={entries}
                  priorityEnabled={summary.priority_enabled}
                  queues={queues}
                  onPriority={(entry, value) => priority.mutate({ entry, value })}
                  onTransfer={(entry, targetQueueId) => {
                    if (
                      window.confirm(
                        `Transfer ticket ${entry.queue_prefix}${entry.queue_number} to another queue?`,
                      )
                    ) {
                      transfer.mutate({ entry, targetQueueId });
                    }
                  }}
                  onAction={(entry, name) => {
                    if (
                      (name === "complete" || name === "skip") &&
                      !window.confirm(`${name} customer ${entry.queue_number}?`)
                    ) {
                      return;
                    }
                    action.mutate({ entry, name });
                  }}
                />
              </div>
            )}
          </>
        )
      )}

      <QueueRequestReviewPanel queues={queues} />
    </PageContainer>
  );
}
