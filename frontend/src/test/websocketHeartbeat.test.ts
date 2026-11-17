import { afterEach, describe, expect, it, vi } from "vitest";

import { startWebSocketHeartbeat } from "../utils/websocketHeartbeat";

describe("WebSocket heartbeat", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("keeps an open socket active and stops when cleaned up", () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", { OPEN: 1 });
    const socket = { readyState: 0, send: vi.fn() };
    const stop = startWebSocketHeartbeat(socket);

    vi.advanceTimersByTime(25_000);
    expect(socket.send).not.toHaveBeenCalled();

    socket.readyState = 1;
    vi.advanceTimersByTime(25_000);
    expect(socket.send).toHaveBeenCalledWith("ping");
    expect(socket.send).toHaveBeenCalledTimes(1);

    stop();
    vi.advanceTimersByTime(25_000);
    expect(socket.send).toHaveBeenCalledTimes(1);
  });
});
