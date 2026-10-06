import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import {
  requestBrowserNotificationPermission,
  useBrowserNotifications,
} from "../hooks/useBrowserNotifications";

afterEach(() => vi.unstubAllGlobals());

describe("browser notification permission", () => {
  it("continues safely when permission is denied", async () => {
    vi.stubGlobal("Notification", { permission: "denied" });
    await expect(requestBrowserNotificationPermission()).resolves.toBe("denied");
  });

  it("keeps queue tracking mounted when notification permission is denied", () => {
    vi.stubGlobal("Notification", { permission: "denied" });
    expect(() =>
      renderHook(() =>
        useBrowserNotifications(
          { event: "CUSTOMER_CALLED", queue_id: "queue-1", data: { id: "entry-1" } },
          "entry-1",
        ),
      ),
    ).not.toThrow();
  });

  it("continues when browser notifications are unsupported", async () => {
    vi.stubGlobal("Notification", undefined);
    await expect(requestBrowserNotificationPermission()).resolves.toBe("unsupported");
  });

  it("shows queue pause and resume events when permission is granted", () => {
    const construct = vi.fn();
    class GrantedNotification {
      static permission = "granted";

      constructor(title: string, options: NotificationOptions) {
        construct(title, options);
      }
    }
    vi.stubGlobal("Notification", GrantedNotification);
    const { rerender } = renderHook(
      ({ event }) => useBrowserNotifications(event, "entry-1"),
      {
        initialProps: {
          event: {
            event: "QUEUE_PAUSED",
            queue_id: "queue-1",
            data: { event_id: "pause-1" },
          },
        },
      },
    );

    rerender({
      event: {
        event: "QUEUE_RESUMED",
        queue_id: "queue-1",
        data: { event_id: "resume-1" },
      },
    });
    rerender({
      event: {
        event: "QUEUE_PAUSED",
        queue_id: "queue-1",
        data: { event_id: "pause-1" },
      },
    });

    expect(construct).toHaveBeenCalledTimes(2);
    expect(construct).toHaveBeenNthCalledWith(
      1,
      "QueueLess: queue paused",
      { body: "Your queue status has changed." },
    );
  });
});
