import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { QueuePosition } from "../../components/customer/QueuePosition";
import { QueueTicket } from "../../components/customer/QueueTicket";
import { WaitTimeCard } from "../../components/customer/WaitTimeCard";
import { cancelQueueEntry, getQueueEntry } from "../../services/queue";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import { useAuthStore } from "../../store/authStore";
import { getWaitTimePrediction } from "../../services/ai";
import { useBrowserNotifications } from "../../hooks/useBrowserNotifications";
import { ApiError } from "../../services/api";
import { useServerClock } from "../../hooks/useServerClock";

export function QueuePage() {
  const { entryId = "" } = useParams();
  const queryClient = useQueryClient();
  const [cancelledMessage, setCancelledMessage] = useState("");
  const token = useAuthStore((state) => state.token);
  const serverNow = useServerClock();
  const query = useQuery({
    queryKey: ["queue-entry", entryId],
    queryFn: () => getQueueEntry(entryId),
  });
  const prediction = useQuery({
    queryKey: ["wait-time-prediction", entryId],
    queryFn: () => getWaitTimePrediction(entryId),
    enabled: !!entryId && !!query.data && !["completed", "skipped", "cancelled"].includes(query.data.status),
  });
  const socket = useQueueWebSocket(query.data?.queue_id, token ?? undefined);
  const requestBrowserNotifications = useBrowserNotifications(socket.event, entryId);
  const cancel = useMutation({
    mutationFn: () => cancelQueueEntry(entryId),
    onSuccess: async () => {
      setCancelledMessage("Your place in the queue has been cancelled.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["queue-entry", entryId] }),
        queryClient.invalidateQueries({ queryKey: ["queue-history"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      ]);
    },
  });
  const estimateUpdatedAt = prediction.dataUpdatedAt || query.dataUpdatedAt;
  const elapsedEstimateMinutes = estimateUpdatedAt
    ? Math.max(0, Math.floor((serverNow.getTime() - estimateUpdatedAt) / 60_000))
    : 0;
  const remainingEstimateMinutes = query.data
    ? Math.max(0, query.data.estimated_wait_minutes - elapsedEstimateMinutes)
    : 0;

  return (
    <PageContainer className="max-w-3xl py-10">
      <h1 className="text-4xl font-black text-ink">Your queue ticket</h1>
      <div className="mt-6 space-y-4">
        {query.isLoading && <LoadingState label="Loading queue status..." />}
        {query.error instanceof Error && (
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        )}
        {query.data && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink/10 bg-white px-4 py-3">
              <p aria-live="polite" className="text-sm text-ink/65">
                Live updates: {socket.status}
              </p>
              <time
                className="text-sm text-ink/65"
                dateTime={serverNow.toISOString()}
                title="Authoritative QueueLess server time"
              >
                Server time {serverNow.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </time>
              <button
                className="rounded-full border border-ink/20 px-4 py-2 text-sm font-bold text-ink transition hover:bg-ink/5 disabled:opacity-60"
                disabled={query.isFetching}
                onClick={() => {
                  void query.refetch();
                  if (prediction.data) void prediction.refetch();
                }}
                type="button"
              >
                {query.isFetching ? "Refreshing..." : "Refresh status"}
              </button>
            </div>
            <QueueTicket position={query.data} />
            {query.data.status === "called" && (
              <section
                className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950"
                role="status"
                aria-live="assertive"
              >
                <h2 className="text-xl font-black">You have been called.</h2>
                <p className="mt-1">
                  Proceed to {query.data.counter?.name ?? "the counter"}.
                </p>
              </section>
            )}
            {query.data.status === "completed" && (
              <p className="rounded-2xl border border-emerald-300 bg-emerald-50 p-5 text-xl font-black text-emerald-950">
                Service completed ✓
              </p>
            )}
            {query.data.transferred_to_entry_id && (
              <p className="rounded-2xl border border-blue-300 bg-blue-50 p-5 text-blue-950">
                Your ticket was transferred.{" "}
                <Link
                  className="font-bold underline"
                  to={`/queue/${query.data.transferred_to_entry_id}`}
                >
                  View your new ticket
                </Link>
              </p>
            )}
            {query.data.status === "waiting" && (
              <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink/10 bg-white p-4">
                <p className="text-sm text-ink/70">
                  Plans changed? You can give up your place while you’re still waiting.
                </p>
                <button
                  className="rounded-full border border-red-200 px-4 py-2 text-sm font-bold text-red-800 transition hover:bg-red-50 disabled:opacity-60"
                  disabled={cancel.isPending}
                  onClick={() => {
                    if (window.confirm("Cancel your place in this queue? This cannot be undone.")) {
                      cancel.mutate();
                    }
                  }}
                  type="button"
                >
                  {cancel.isPending ? "Cancelling..." : "Cancel my place"}
                </button>
              </section>
            )}
            {cancelledMessage && (
              <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900" role="status">
                {cancelledMessage}
              </p>
            )}
            {cancel.error && (
              <p className="rounded-xl bg-red-50 p-3 text-sm text-red-900" role="alert">
                {cancel.error instanceof ApiError
                  ? cancel.error.detail
                  : "Unable to cancel your place. Please try again."}
              </p>
            )}
            <button className="text-sm font-semibold text-emerald-800" onClick={() => void requestBrowserNotifications()}>Enable browser notifications</button>
            <QueuePosition position={query.data} />
            <WaitTimeCard
              estimatedWaitMinutes={remainingEstimateMinutes}
              refreshedAt={prediction.dataUpdatedAt}
              prediction={prediction.data}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
