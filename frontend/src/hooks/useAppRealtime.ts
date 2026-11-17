import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { captureWebSocketFailure } from "../observability";
import { apiRequest, WS_BASE } from "../services/api";
import { startWebSocketHeartbeat } from "../utils/websocketHeartbeat";

function reconnectDelay(attempt: number) {
  return Math.random() * Math.min(30_000, 1_000 * 2 ** attempt);
}

export function useAppRealtime(token: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!token) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retryCount = 0;
    let retryTimer: number | undefined;
    let stopHeartbeat = () => {};

    const reconnect = () => {
      if (stopped) return;
      if (retryCount >= 2) captureWebSocketFailure();
      retryTimer = window.setTimeout(() => void connect(), reconnectDelay(retryCount++));
    };

    const connect = async () => {
      try {
        const { ticket } = await apiRequest<{ ticket: string }>(
          "/api/v1/auth/app-updates-ws-ticket",
          { method: "POST" },
          token,
        );
        if (stopped) return;
        socket = new WebSocket(
          `${WS_BASE}/ws/app-updates?${new URLSearchParams({ ticket })}`,
        );
        const activeSocket = socket;
        socket.onopen = () => {
          retryCount = 0;
          stopHeartbeat();
          stopHeartbeat = startWebSocketHeartbeat(activeSocket);
          void queryClient.invalidateQueries();
        };
        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data) as { event?: unknown };
            if (event.event === "app.data_changed") {
              void queryClient.invalidateQueries();
            }
          } catch (error) {
            console.error("Unable to read a QueueLess app update.", error);
          }
        };
        socket.onclose = (event) => {
          stopHeartbeat();
          stopHeartbeat = () => {};
          if (!stopped) {
            if ([1006, 1011, 1012, 1013].includes(event.code) && retryCount >= 2) {
              captureWebSocketFailure();
            }
            reconnect();
          }
        };
        socket.onerror = () => activeSocket.close();
      } catch {
        reconnect();
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      stopHeartbeat();
      socket?.close();
    };
  }, [queryClient, token]);
}