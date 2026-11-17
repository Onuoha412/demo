import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { LoadingState } from "./LoadingState";
import { useAuthStore } from "../../store/authStore";
import {
  getAnnouncementWebSocketTicket,
  getPublishedAnnouncements,
} from "../../services/operations";
import { WS_BASE } from "../../services/api";
import { startWebSocketHeartbeat } from "../../utils/websocketHeartbeat";

export function AnnouncementFeed() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [connection, setConnection] = useState<"connecting" | "connected" | "reconnecting">(
    "connecting",
  );
  const announcements = useQuery({
    queryKey: ["announcements", "published"],
    queryFn: () => getPublishedAnnouncements(token!),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (!token) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryCount = 0;
    let stopHeartbeat = () => {};

    const reconnect = () => {
      if (stopped) return;
      setConnection("reconnecting");
      const delay = Math.min(30_000, 1_000 * 2 ** retryCount++);
      retryTimer = window.setTimeout(() => void connect(), delay);
    };
    const connect = async () => {
      setConnection("connecting");
      try {
        const { ticket } = await getAnnouncementWebSocketTicket(token);
        if (stopped) return;
        socket = new WebSocket(
          `${WS_BASE}/ws/announcements?${new URLSearchParams({ ticket })}`,
        );
        const activeSocket = socket;
        socket.onopen = () => {
          stopHeartbeat();
          stopHeartbeat = startWebSocketHeartbeat(activeSocket);
          retryCount = 0;
          setConnection("connected");
          void queryClient.invalidateQueries({ queryKey: ["announcements", "published"] });
        };
        socket.onmessage = (message) => {
          void queryClient.invalidateQueries({ queryKey: ["announcements", "published"] });
          try {
            const event = JSON.parse(message.data) as { event?: unknown };
            if (
              typeof event.event === "string" &&
              event.event.startsWith("QUEUE_REQUEST_")
            ) {
              void queryClient.invalidateQueries({ queryKey: ["queue-requests"] });
            }
          } catch (error) {
            console.error("Unable to read a QueueLess announcement event.", error);
          }
        };
        socket.onclose = () => {
          stopHeartbeat();
          stopHeartbeat = () => {};
          reconnect();
        };
        socket.onerror = () => socket?.close();
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

  if (!token) return null;
  if (announcements.isLoading) {
    return <LoadingState label="Checking announcements..." />;
  }
  if (announcements.isError) {
    return (
      <p className="mx-auto my-4 max-w-6xl px-4 text-sm text-red-800" role="alert">
        Announcements could not be loaded.{" "}
        <button className="font-bold underline" onClick={() => void announcements.refetch()}>
          Retry
        </button>
      </p>
    );
  }
  if (!announcements.data?.length) return null;

  return (
    <section aria-label="Announcements" className="mx-auto max-w-6xl space-y-3 px-4 py-5">
      <p className="text-xs text-ink/55" aria-live="polite">
        Announcement updates: {connection}
      </p>
      {announcements.data.map((announcement) => (
        <article
          className="rounded-2xl border border-emerald-900/10 bg-emerald-50 p-5"
          key={announcement.id}
        >
          <h2 className="font-bold text-emerald-950">{announcement.title}</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink/80">
            {announcement.body}
          </p>
          <p className="mt-2 text-xs text-ink/55">
            Published {new Date(announcement.published_at!).toLocaleString()}
          </p>
        </article>
      ))}
    </section>
  );
}
