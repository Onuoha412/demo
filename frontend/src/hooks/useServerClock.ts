import { useEffect, useState } from "react";

type TimeResponse = {
  server_time: string;
};

const RESYNC_INTERVAL_MS = 60_000;

export function useServerClock() {
  const [serverOffset, setServerOffset] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (import.meta.env.MODE === "test") return;
    let active = true;
    const synchronize = async () => {
      try {
        const response = await fetch("/api/v1/time/now");
        if (!response.ok) throw new Error(`Time sync failed with ${response.status}`);
        const payload = (await response.json()) as TimeResponse;
        const serverTime = Date.parse(payload.server_time);
        if (!Number.isNaN(serverTime) && active) {
          setServerOffset(serverTime - Date.now());
        }
      } catch (error) {
        console.error("Unable to synchronize the QueueLess clock.", error);
      }
    };
    void synchronize();
    const syncTimer = window.setInterval(() => void synchronize(), RESYNC_INTERVAL_MS);
    const tickTimer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      active = false;
      window.clearInterval(syncTimer);
      window.clearInterval(tickTimer);
    };
  }, []);

  return new Date(now + serverOffset);
}
