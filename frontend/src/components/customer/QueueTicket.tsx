import type { QueuePosition } from "../../types/api";
import { formatQueueNumber } from "../../utils/queueNumber";

export function QueueTicket({ position }: { position: QueuePosition }) {
  return (
    <section className="rounded-3xl bg-ink p-8 text-center text-cream">
      <p className="text-sm uppercase tracking-wide text-cream/70">Your queue number</p>
      <p className="mt-3 text-7xl font-black tracking-tight">
        {formatQueueNumber(position.queue_prefix, position.queue_number)}
      </p>
      <p className="mt-3 text-sm text-cream/70">Status: {position.status.toUpperCase()}</p>
      {position.request_note && (
        <p className="mt-3 text-sm text-cream/80">
          Your request: {position.request_note}
        </p>
      )}
      <p className="mt-2 text-sm text-cream/70">
        {position.verified_at ? "Request verified" : "Request awaiting verification"}
      </p>
    </section>
  );
}
