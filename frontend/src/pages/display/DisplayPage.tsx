import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getQueue } from "../../services/queue";
import { useQueueWebSocket } from "../../hooks/useQueueWebSocket";
import { PageContainer } from "../../components/common/PageContainer";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { formatQueueNumber } from "../../utils/queueNumber";

export function DisplayPage() {
  const { queueId = "" } = useParams();
  const query = useQuery({ queryKey: ["public-queue", queueId], queryFn: () => getQueue(queueId), enabled: !!queueId });
  const connection = useQueueWebSocket(queueId);
  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) return <ErrorState message="Unable to load this queue display." />;
  const active = query.data.entries.filter((entry) => entry.status === "called" || entry.status === "serving");
  const waiting = query.data.entries.filter((entry) => entry.status === "waiting").slice(0, 5);
  return <PageContainer className="py-10"><div className="flex items-center justify-between"><div><p className="text-sm uppercase tracking-widest text-emerald-800">QueueLess</p><h1 className="text-5xl font-black">{query.data.name}</h1></div><span className="rounded-full bg-ink px-4 py-2 text-sm text-white">{connection.status}</span></div>
    <div className="mt-10 grid gap-6 lg:grid-cols-2"><section className="rounded-3xl bg-ink p-10 text-center text-cream"><p className="text-lg uppercase text-cream/70">Now serving</p><p className="mt-4 text-8xl font-black">{active[0] ? formatQueueNumber(query.data.prefix, active[0].queue_number) : "—"}</p><p className="mt-4 text-xl uppercase">{active[0]?.counter?.name ?? "Please wait"}</p></section>
    <section className="rounded-3xl bg-white p-8"><h2 className="text-2xl font-black">Next customers</h2><ol className="mt-4 space-y-3">{waiting.map((entry) => <li className="flex justify-between rounded-xl bg-ink/5 p-4 text-2xl font-bold" key={entry.id}><span>{formatQueueNumber(query.data.prefix, entry.queue_number)}</span><span className="text-base font-normal text-ink/60">{entry.estimated_wait_minutes} min</span></li>)}</ol><p className="mt-6 capitalize text-emerald-800">Queue status: {query.data.status}</p></section></div></PageContainer>;
}
