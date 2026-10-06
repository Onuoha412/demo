import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageContainer } from "../../components/common/PageContainer";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { useAuthStore } from "../../store/authStore";
import { getStaffDashboard, getStaffQueue, nextCustomer, setQueueStatus, staffAction } from "../../services/staff";
import { StatsCard, QueueStatusBadge, CurrentCustomerCard } from "../../components/staff/StaffCards";
import { StaffQueueTable } from "../../components/staff/StaffQueueTable";
import type { QueuePosition } from "../../types/api";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";

export function StaffDashboardPage() {
  const token = useAuthStore((s) => s.token)!; const client = useQueryClient();
  const dashboard = useQuery({ queryKey: ["staff-dashboard"], queryFn: () => getStaffDashboard(token), refetchInterval: 15000 });
  const queueId = dashboard.data?.queues[0]?.id;
  const connection = useQueueWebSocket(queueId, token);
  const queue = useQuery({ queryKey: ["staff-queue", queueId], queryFn: () => getStaffQueue(queueId!, token), enabled: !!queueId });
  const action = useMutation({ mutationFn: ({ entry, name }: { entry: QueuePosition; name: "call" | "start" | "complete" | "skip" }) => staffAction(entry.id, name, token), onSuccess: () => { void client.invalidateQueries({ queryKey: ["staff-dashboard"] }); void client.invalidateQueries({ queryKey: ["staff-queue", queueId] }); } });
  const next = useMutation({ mutationFn: () => nextCustomer(queueId!, token), onSuccess: () => { void client.invalidateQueries({ queryKey: ["staff-dashboard"] }); void client.invalidateQueries({ queryKey: ["staff-queue", queueId] }); } });
  const status = useMutation({ mutationFn: (value: "pause" | "resume") => setQueueStatus(queueId!, value, token), onSuccess: () => void client.invalidateQueries({ queryKey: ["staff-dashboard"] }) });
  if (dashboard.isLoading) return <LoadingState />;
  if (dashboard.isError || !dashboard.data) return <ErrorState message="Unable to load the staff dashboard." />;
  const summary = dashboard.data.queues[0]; const entries = queue.data?.entries ?? [];
  return <PageContainer className="py-10"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm text-ink/60">{dashboard.data.branch?.name}</p><h1 className="text-4xl font-black">Staff dashboard</h1></div><div className="flex items-center gap-3">{connection.status !== "connected" && <span className="text-xs text-amber-700">Live updates: {connection.status}</span>}{summary && <QueueStatusBadge status={summary.status} />}</div></div>
    {summary && <><div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatsCard label="Waiting" value={summary.waiting_count}/><StatsCard label="Serving" value={summary.serving_count}/><StatsCard label="Completed" value={summary.completed_count}/><StatsCard label="Skipped" value={summary.skipped_count}/></div>
    <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_2fr]"><CurrentCustomerCard number={entries.find((e) => e.status === "serving" || e.status === "called")?.queue_number} status={entries.find((e) => e.status === "serving" || e.status === "called")?.status}/><div className="rounded-2xl border border-ink/10 bg-white p-6"><h2 className="text-xl font-black">{summary.name}</h2><div className="mt-4 flex flex-wrap gap-3"><button className="rounded-full bg-ink px-4 py-2 text-sm font-bold text-white" onClick={() => next.mutate()} disabled={next.isPending}>Next</button><button className="rounded-full border px-4 py-2 text-sm font-bold" onClick={() => status.mutate(summary.status === "paused" ? "resume" : "pause")}>{summary.status === "paused" ? "Resume queue" : "Pause queue"}</button></div></div></div>
    <div className="mt-8"><StaffQueueTable entries={entries} onAction={(entry, name) => { if ((name === "complete" || name === "skip") && !window.confirm(`${name} customer ${entry.queue_number}?`)) return; action.mutate({ entry, name }); }} /></div></>}</PageContainer>;
}
