import type { QueuePosition } from "../../types/api";
import { formatQueueNumber } from "../../utils/queueNumber";
import { Button } from "../common/Button";

export function StaffQueueTable({ entries, onAction }: { entries: QueuePosition[]; onAction: (entry: QueuePosition, action: "call" | "start" | "complete" | "skip") => void }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-ink/10 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-ink/5"><tr><th className="p-4">Number</th><th className="p-4">Status</th><th className="p-4">Ahead</th><th className="p-4">Action</th></tr></thead>
        <tbody>{entries.map((entry) => <tr className="border-t border-ink/10" key={entry.id}>
          <td className="p-4 font-black">{formatQueueNumber(entry.queue_prefix, entry.queue_number)}</td><td className="p-4 capitalize">{entry.status}</td><td className="p-4">{entry.people_ahead}</td>
          <td className="flex gap-2 p-4">{entry.status !== "completed" && entry.status !== "skipped" && entry.status !== "cancelled" && <>{entry.status === "called" ? <><Button variant="secondary" onClick={() => onAction(entry, "start")}>Start</Button><Button variant="secondary" onClick={() => onAction(entry, "complete")}>Complete</Button><Button variant="secondary" onClick={() => onAction(entry, "skip")}>Skip</Button></> : <Button variant="secondary" onClick={() => onAction(entry, entry.status === "waiting" ? "call" : "complete")}>{entry.status === "waiting" ? "Call" : "Complete"}</Button>}</>}</td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
