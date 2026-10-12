import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_BASE, apiRequest } from "../services/api";
import { captureWebSocketFailure } from "../observability";

export type QueueSocketEvent = {
  event: string;
  queue_id: string;
  data?: Record<string, unknown>;
  timestamp?: string;
};

function socketUrl(queueId: string, ticket?: string) {
  const base =
    import.meta.env.VITE_WS_URL ||
    (API_BASE
      ? API_BASE.replace(/^http/, "ws")
      : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`);
  const params = ticket ? `?ticket=${encodeURIComponent(ticket)}` : "?public=1";
  return `${base.replace(/\/$/, "")}/ws/queues/${queueId}${params}`;
}

export function useQueueWebSocket(queueId: string | undefined, token?: string) {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const lastEventRef = useRef<number | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected" | "stale">("disconnected");
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  const [event, setEvent] = useState<QueueSocketEvent | undefined>();

  useEffect(() => {
    if (!queueId) return;
    let stopped = false;
    let retryTimer: number | undefined;
    const staleTimer = window.setInterval(() => {
      if (lastEventRef.current && Date.now() - lastEventRef.current > 60000) setStatus("stale");
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
      const socket = new WebSocket(socketUrl(queueId, response?.ticket));
      socketRef.current = socket;
      socket.onopen = () => { retryRef.current = 0; setStatus("connected"); };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as QueueSocketEvent;
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
          void queryClient.invalidateQueries({ queryKey: ["queue-entry"] });
          void queryClient.invalidateQueries({ queryKey: ["wait-time-prediction"] });
          void queryClient.invalidateQueries({ queryKey: ["staff-dashboard"] });
          void queryClient.invalidateQueries({ queryKey: ["staff-queue", queueId] });
          void queryClient.invalidateQueries({ queryKey: ["admin-queue", queueId] });
          void queryClient.invalidateQueries({ queryKey: ["public-queue", queueId] });
          void queryClient.invalidateQueries({ queryKey: ["notifications"] });
          if (event.data) queryClient.setQueryData(["queue-event", queueId], event);
        } catch { setStatus("stale"); }
      };
      socket.onclose = (closeEvent) => {
        socketRef.current = null;
        if (stopped) return;
        setStatus("disconnected");
        if (
          [1006, 1011, 1012, 1013].includes(closeEvent.code) &&
          retryRef.current >= 2
        ) {
          captureWebSocketFailure();
        }
        const delay = Math.min(30000, 1000 * 2 ** retryRef.current++);
        retryTimer = window.setTimeout(() => void connect(), delay);
      };
      socket.onerror = () => socket.close();
      } catch {
        if (stopped) return;
        setStatus("disconnected");
        const delay = Math.min(30000, 1000 * 2 ** retryRef.current++);
        retryTimer = window.setTimeout(() => void connect(), delay);
      }
    };
    void connect();
    return () => {
      stopped = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (staleTimer) window.clearInterval(staleTimer);
      socketRef.current?.close();
    };
  }, [queueId, token, queryClient]);

  return { status, lastEventAt, event };
}
