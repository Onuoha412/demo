import type { QueuePosition } from "../../types/api";
import { formatQueueNumber } from "../../utils/queueNumber";
import { Button } from "../common/Button";

export function StaffQueueTable({
  entries,
  onAction,
  priorityEnabled,
  onPriority,
  queues,
  onTransfer,
}: {
  entries: QueuePosition[];
  onAction: (entry: QueuePosition, action: "call" | "start" | "complete" | "skip") => void;
  priorityEnabled?: boolean;
  onPriority?: (entry: QueuePosition, priority: number) => void;
  queues?: { id: string; name: string }[];
  onTransfer?: (entry: QueuePosition, targetQueueId: string) => void;
}) {
  const canTransfer = (queues?.length ?? 0) > 1;
  return (
    <div className="overflow-x-auto rounded-2xl border border-ink/10 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-ink/5"><tr><th className="p-4">Number</th><th className="p-4">Status</th><th className="p-4">Ahead</th>{priorityEnabled && <th className="p-4">Priority</th>}{canTransfer && <th className="p-4">Transfer</th>}<th className="p-4">Action</th></tr></thead>
        <tbody>{entries.map((entry) => <tr className="border-t border-ink/10" key={entry.id}>
          <td className="p-4 font-black">{formatQueueNumber(entry.queue_prefix, entry.queue_number)}</td><td className="p-4 capitalize">{entry.status}</td><td className="p-4">{entry.people_ahead}</td>
          {priorityEnabled && <td className="p-4">
            {entry.status === "waiting" ? (
              <select
                aria-label={`Priority for ${formatQueueNumber(entry.queue_prefix, entry.queue_number)}`}
                className="rounded-lg border px-2 py-1"
                value={entry.priority ?? 0}
                onChange={(event) => onPriority?.(entry, Number(event.target.value))}
              >
                {[0, 1, 2, 3, 4, 5].map((priority) => (
                  <option key={priority} value={priority}>{priority === 0 ? "Standard" : `Level ${priority}`}</option>
                ))}
              </select>
            ) : (entry.priority ?? 0) > 0 ? `Level ${entry.priority}` : "Standard"}
          </td>}
          {canTransfer && <td className="p-4">
            {entry.status === "waiting" && (
              <select
                aria-label={`Transfer ${formatQueueNumber(entry.queue_prefix, entry.queue_number)}`}
                className="rounded-lg border px-2 py-1"
                value=""
                onChange={(event) => onTransfer?.(entry, event.target.value)}
              >
                <option value="">Choose queue</option>
                {queues?.filter((queue) => queue.id !== entry.queue_id).map((queue) => (
                  <option key={queue.id} value={queue.id}>{queue.name}</option>
                ))}
              </select>
            )}
          </td>}
          <td className="flex gap-2 p-4">{entry.status !== "completed" && entry.status !== "skipped" && entry.status !== "cancelled" && <>{entry.status === "called" ? <><Button variant="secondary" onClick={() => onAction(entry, "start")}>Start</Button><Button variant="secondary" onClick={() => onAction(entry, "complete")}>Complete</Button><Button variant="secondary" onClick={() => onAction(entry, "skip")}>Skip</Button></> : <Button variant="secondary" onClick={() => onAction(entry, entry.status === "waiting" ? "call" : "complete")}>{entry.status === "waiting" ? "Call" : "Complete"}</Button>}</>}</td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
