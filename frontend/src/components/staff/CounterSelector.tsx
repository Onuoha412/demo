import type { StaffCounter } from "../../types/api";

export function CounterSelector({ counters, value, onChange }: { counters: StaffCounter[]; value: string; onChange: (value: string) => void }) {
  return <label className="text-sm font-semibold">Counter<select className="ml-2 rounded-lg border px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)}><option value="">Select counter</option>{counters.map((counter) => <option key={counter.id} value={counter.id}>{counter.name}</option>)}</select></label>;
}
