import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useQueueWebSocket = vi.hoisted(() => vi.fn());

vi.mock("../hooks/useQueueWebSocket", () => ({ useQueueWebSocket }));

import { QueueRealtimeSubscriptions } from "../components/common/QueueRealtimeSubscriptions";

describe("QueueRealtimeSubscriptions", () => {
  it("subscribes once to each queue except the already subscribed queue", () => {
    const { rerender } = render(
      <QueueRealtimeSubscriptions
        queueIds={["queue-1", "queue-2", "queue-2"]}
        token="staff-session"
        excludeQueueId="queue-1"
      />,
    );

    expect(useQueueWebSocket).toHaveBeenCalledTimes(1);
    expect(useQueueWebSocket).toHaveBeenCalledWith("queue-2", "staff-session");

    rerender(
      <QueueRealtimeSubscriptions
        queueIds={["queue-2", "queue-3"]}
        token="staff-session"
      />,
    );

    expect(useQueueWebSocket).toHaveBeenCalledWith("queue-3", "staff-session");
    expect(useQueueWebSocket).toHaveBeenCalledTimes(3);
  });
});
