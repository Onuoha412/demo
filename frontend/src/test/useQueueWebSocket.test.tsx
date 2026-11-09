import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";

import { useQueueWebSocket } from "../hooks/useQueueWebSocket";

class TestWebSocket {
  static instance: TestWebSocket | undefined;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(readonly url: string) {
    TestWebSocket.instance = this;
  }

  close() {}

  connect() {
    this.onopen?.(new Event("open"));
  }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  TestWebSocket.instance = undefined;
});

it("refetches queue-backed queries when the socket reconnects", async () => {
  vi.stubGlobal("WebSocket", TestWebSocket);
  const queryClient = new QueryClient();
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result, unmount } = renderHook(
    () => useQueueWebSocket("queue-1"),
    { wrapper },
  );

  await waitFor(() => expect(TestWebSocket.instance).toBeDefined());
  act(() => TestWebSocket.instance?.connect());

  await waitFor(() => expect(result.current.status).toBe("connected"));
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["queue-entry"] });
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ["staff-queue", "queue-1"],
  });
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ["public-queue", "queue-1"],
  });
  unmount();
});

it("uses randomized exponential backoff when reconnecting", async () => {
  vi.stubGlobal("WebSocket", TestWebSocket);
  vi.spyOn(Math, "random").mockReturnValue(0.5);
  const queryClient = new QueryClient();
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { unmount } = renderHook(() => useQueueWebSocket("queue-1"), { wrapper });

  await waitFor(() => expect(TestWebSocket.instance).toBeDefined());
  const firstSocket = TestWebSocket.instance;
  vi.useFakeTimers();
  act(() => {
    firstSocket?.onclose?.(new CloseEvent("close", { code: 1006 }));
  });
  act(() => vi.advanceTimersByTime(499));
  expect(TestWebSocket.instance).toBe(firstSocket);
  act(() => vi.advanceTimersByTime(1));
  expect(TestWebSocket.instance).not.toBe(firstSocket);

  unmount();
  vi.useRealTimers();
});
