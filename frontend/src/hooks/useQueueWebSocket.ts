import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_BASE, apiRequest } from "../services/api";
import { captureWebSocketFailure } from "../observability";

export type QueueSocketEvent = {
  event: string;
  queue_id: string;
  data?: Record<string, unknown>;
  event_id?: string;
  event_sequence?: number;
  event_version?: number;
  timestamp?: string;
};

function reconnectDelay(attempt: number) {
  return Math.random() * Math.min(30000, 1000 * 2 ** attempt);
}

function socketUrl(queueId: string, ticket?: string, since?: number) {
  const params = new URLSearchParams(ticket ? { ticket } : { public: "1" });
  if (since !== undefined) params.set("since", String(since));
  return `${WS_BASE}/ws/queues/${queueId}?${params.toString()}`;
}

export function useQueueWebSocket(queueId: string | undefined, token?: string) {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const lastEventRef = useRef<number | null>(null);
  const connectedAtRef = useRef<number | null>(null);
  const lastSequenceRef = useRef<number | undefined>(undefined);
  const seenEventIdsRef = useRef<Set<string>>(new Set());
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected" | "stale">("disconnected");
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  const [event, setEvent] = useState<QueueSocketEvent | undefined>();
  const refreshQueueState = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["queue-entry"] });
    void queryClient.invalidateQueries({ queryKey: ["queue-history"] });
    void queryClient.invalidateQueries({ queryKey: ["wait-time-prediction"] });
    void queryClient.invalidateQueries({ queryKey: ["staff-dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["staff-queue", queueId] });
    void queryClient.invalidateQueries({ queryKey: ["admin-queue", queueId] });
    void queryClient.invalidateQueries({ queryKey: ["admin-analytics"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "queue-options"] });
    void queryClient.invalidateQueries({ queryKey: ["public-queue", queueId] });
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    void queryClient.invalidateQueries({ queryKey: ["queue-requests"] });
  }, [queryClient, queueId]);

  useEffect(() => {
    if (!queueId) return;
    let stopped = false;
    let retryTimer: number | undefined;
    const staleTimer = window.setInterval(() => {
      const lastActivity = lastEventRef.current ?? connectedAtRef.current;
      if (lastActivity && Date.now() - lastActivity > 60000) {
        setStatus("stale");
        socketRef.current?.close();
      }
    }, 10000);
    const connect = async () => {
      if (stopped) return;
      setStatus("connecting");
      try {
      const response = token
        ? await apiRequest<{ ticket: string }>("/api/v1/auth/ws-ticket", {
          method: "POST",
          body: JSON.stringify({ queue_id: queueId }),
        }, token)
        : undefined;
      if (stopped) return;
      const socket = new WebSocket(
        socketUrl(queueId, response?.ticket, lastSequenceRef.current),
      );
      socketRef.current = socket;
      socket.onopen = () => {
        retryRef.current = 0;
        connectedAtRef.current = Date.now();
        setStatus("connected");
        refreshQueueState();
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as QueueSocketEvent;
          if (event.event_id && seenEventIdsRef.current.has(event.event_id)) return;
          if (event.event_id) seenEventIdsRef.current.add(event.event_id);
          if (event.event_sequence !== undefined) {
            lastSequenceRef.current = Math.max(
              lastSequenceRef.current ?? 0,
              event.event_sequence,
            );
          }
          setEvent(event);
          if ("BroadcastChannel" in window) {
            const channel = new BroadcastChannel("queueless:queue-events");
            channel.postMessage({ queue_id: event.queue_id, event: event.event });
            channel.close();
          }
          const receivedAt = Date.now();
          lastEventRef.current = receivedAt;
          setLastEventAt(receivedAt);
          setStatus("connected");
          refreshQueueState();
          if (event.data) queryClient.setQueryData(["queue-event", queueId], event);
        } catch { setStatus("stale"); }
      };
      socket.onclose = (closeEvent) => {
        socketRef.current = null;
        connectedAtRef.current = null;
        if (stopped) return;
        setStatus("disconnected");
        if (
          [1006, 1011, 1012, 1013].includes(closeEvent.code) &&
          retryRef.current >= 2
        ) {
          captureWebSocketFailure();
        }
        const delay = reconnectDelay(retryRef.current++);
        retryTimer = window.setTimeout(() => void connect(), delay);
      };
      socket.onerror = () => socket.close();
      } catch {
        if (stopped) return;
        setStatus("disconnected");
        const delay = reconnectDelay(retryRef.current++);
        retryTimer = window.setTimeout(() => void connect(), delay);
      }
    };
    void connect();
    return () => {
      stopped = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (staleTimer) window.clearInterval(staleTimer);
      connectedAtRef.current = null;
      socketRef.current?.close();
    };
  }, [queueId, token, queryClient, refreshQueueState]);

  useEffect(() => {
    if (!queueId || status === "connected") return;
    const recoveryTimer = window.setInterval(refreshQueueState, 15000);
    refreshQueueState();
    return () => window.clearInterval(recoveryTimer);
  }, [queueId, refreshQueueState, status]);

  return { status, lastEventAt, event };
}
