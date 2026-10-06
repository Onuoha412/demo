import { useCallback, useEffect, useRef } from "react";
import type { QueueSocketEvent } from "./useQueueWebSocket";

export async function requestBrowserNotificationPermission(): Promise<NotificationPermission | "unsupported"> {
  if (typeof Notification === "undefined") return "unsupported";
  if (Notification.permission !== "default") return Notification.permission;
  try { return await Notification.requestPermission(); } catch { return "denied"; }
}

export function useBrowserNotifications(event?: QueueSocketEvent, entryId?: string) {
  const deliveredEvents = useRef(new Set<string>());
  useEffect(() => {
    if (!event || typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const isQueueStatusEvent = ["QUEUE_PAUSED", "QUEUE_RESUMED"].includes(event.event);
    const targetEntry = event.data?.queue_entry_id ?? event.data?.id;
    if (!entryId || (!isQueueStatusEvent && targetEntry !== entryId)) return;
    if (![
      "CUSTOMER_CALLED",
      "QUEUE_APPROACHING",
      "SERVICE_COMPLETED",
      "QUEUE_PAUSED",
      "QUEUE_RESUMED",
    ].includes(event.event)) return;
    const eventId = String(event.data?.event_id ?? `${entryId}:${event.event}`);
    if (deliveredEvents.current.has(eventId)) return;
    deliveredEvents.current.add(eventId);
    const title = event.event.replaceAll("_", " ").toLowerCase();
    try {
      new Notification(`QueueLess: ${title}`, {
        body: isQueueStatusEvent ? "Your queue status has changed." : "Your turn status has changed.",
      });
    } catch {
      // Browser notifications are optional; a platform error must not affect queue tracking.
    }
  }, [event, entryId]);
  return useCallback(async () => {
    await requestBrowserNotificationPermission();
  }, []);
}
