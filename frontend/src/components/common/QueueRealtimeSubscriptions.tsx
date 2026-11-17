import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";

function QueueRealtimeSubscription({
  queueId,
  token,
}: {
  queueId: string;
  token?: string;
}) {
  useQueueWebSocket(queueId, token);
  return null;
}

export function QueueRealtimeSubscriptions({
  queueIds,
  token,
  excludeQueueId,
}: {
  queueIds: string[];
  token?: string;
  excludeQueueId?: string;
}) {
  const subscriptions = [...new Set(queueIds)].filter(
    (queueId) => queueId && queueId !== excludeQueueId,
  );

  return subscriptions.map((queueId) => (
    <QueueRealtimeSubscription key={queueId} queueId={queueId} token={token} />
  ));
}
