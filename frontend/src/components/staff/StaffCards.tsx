import { formatQueueNumber } from "../../utils/queueNumber";

export function StatsCard({ label, value }: { label: string; value: number }) {
  return <div className="rounded-2xl border border-ink/10 bg-white p-5"><p className="text-sm text-ink/60">{label}</p><p className="mt-2 text-3xl font-black">{value}</p></div>;
}

export function QueueStatusBadge({ status }: { status: string }) {
  return <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold capitalize text-emerald-900">{status}</span>;
}

export function CurrentCustomerCard({ number, prefix, status }: { number?: number; prefix?: string; status?: string }) {
  return <div className="rounded-2xl bg-ink p-6 text-cream"><p className="text-sm text-cream/70">Current customer</p><p className="mt-2 text-4xl font-black">{number === undefined ? "None" : formatQueueNumber(prefix ?? "", number)}</p>{status && <p className="mt-2 capitalize">{status}</p>}</div>;
}
