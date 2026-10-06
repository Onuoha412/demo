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
    refetchInterval: 15000,
  });
  const prediction = useQuery({
    queryKey: ["wait-time-prediction", entryId],
    queryFn: () => getWaitTimePrediction(entryId),
    enabled: !!entryId && !!query.data && !["completed", "skipped", "cancelled"].includes(query.data.status),
    refetchInterval: 30000,
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
