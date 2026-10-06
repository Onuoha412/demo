import type { QueuePosition as QueuePositionType } from "../../types/api";

export function QueuePosition({ position }: { position: QueuePositionType }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="rounded-2xl border border-ink/10 bg-white p-5">
        <p className="text-xs uppercase tracking-wide text-ink/50">People ahead</p>
        <p className="mt-2 text-3xl font-black text-ink">{position.people_ahead}</p>
      </div>
      <div className="rounded-2xl border border-ink/10 bg-white p-5">
        <p className="text-xs uppercase tracking-wide text-ink/50">Estimated wait</p>
        <p className="mt-2 text-3xl font-black text-ink">
          {position.estimated_wait_minutes} min
        </p>
      </div>
      <div className="rounded-2xl border border-ink/10 bg-white p-5">
        <p className="text-xs uppercase tracking-wide text-ink/50">Counter</p>
        <p className="mt-2 text-2xl font-black text-ink">
          {position.counter ? `${position.counter.name}` : "Pending call"}
        </p>
      </div>
    </div>
  );
}
