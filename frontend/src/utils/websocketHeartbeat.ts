const HEARTBEAT_INTERVAL_MS = 25_000;

export function startWebSocketHeartbeat(
  socket: Pick<WebSocket, "readyState" | "send">,
): () => void {
  const interval = window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, HEARTBEAT_INTERVAL_MS);

  return () => window.clearInterval(interval);
}
