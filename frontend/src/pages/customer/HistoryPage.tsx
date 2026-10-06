import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { getHistory } from "../../services/queue";

export function HistoryPage() {
  const query = useQuery({
    queryKey: ["queue-history"],
    queryFn: () => getHistory(1, 50),
  });

  return (
    <PageContainer className="py-10">
      <h1 className="text-4xl font-black text-ink">Queue history</h1>
      <div className="mt-6 space-y-3">
        {query.isLoading && <LoadingState label="Loading history..." />}
        {query.error instanceof Error && (
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        )}
        {query.data && query.data.items.length === 0 && (
          <EmptyState title="No history yet" message="Join a service queue to see your history here." />
        )}
        {(query.data?.items ?? []).map((item) => (
          <article key={item.entry_id} className="rounded-2xl border border-ink/10 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-bold text-ink">{item.queue_name}</p>
                <p className="text-xs text-ink/60">Joined {new Date(item.joined_at).toLocaleString()}</p>
              </div>
              <span className="rounded-full bg-ink/5 px-3 py-1 text-xs font-semibold text-ink">
                {item.queue_prefix}
                {item.queue_number}
              </span>
            </div>
            <p className="mt-3 text-sm text-ink/70">Status: {item.status}</p>
            <Link to={`/queue/${item.entry_id}`} className="mt-4 inline-block text-sm font-semibold text-emerald-700">
              View latest position
            </Link>
          </article>
        ))}
      </div>
    </PageContainer>
  );
}
