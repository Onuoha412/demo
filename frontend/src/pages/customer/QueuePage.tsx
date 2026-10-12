import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { QueuePosition } from "../../components/customer/QueuePosition";
import { QueueTicket } from "../../components/customer/QueueTicket";
import { WaitTimeCard } from "../../components/customer/WaitTimeCard";
import { getQueueEntry } from "../../services/queue";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import { useAuthStore } from "../../store/authStore";
import { getWaitTimePrediction } from "../../services/ai";
import { useBrowserNotifications } from "../../hooks/useBrowserNotifications";

export function QueuePage() {
  const { entryId = "" } = useParams();
  const token = useAuthStore((state) => state.token);
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
            <button className="text-sm font-semibold text-emerald-800" onClick={() => void requestBrowserNotifications()}>Enable browser notifications</button>
            <QueuePosition position={query.data} />
            <WaitTimeCard
              estimatedWaitMinutes={query.data.estimated_wait_minutes}
              refreshedAt={prediction.dataUpdatedAt}
              prediction={prediction.data}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
