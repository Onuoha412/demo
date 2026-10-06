import type { QueuePosition } from "../../types/api";

export function QueueTicket({ position }: { position: QueuePosition }) {
  return (
    <section className="rounded-3xl bg-ink p-8 text-center text-cream">
      <p className="text-sm uppercase tracking-wide text-cream/70">Your queue number</p>
      <p className="mt-3 text-7xl font-black tracking-tight">{position.queue_number}</p>
      <p className="mt-3 text-sm text-cream/70">Status: {position.status.toUpperCase()}</p>
    </section>
  );
}
