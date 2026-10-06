import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { getService } from "../../services/queue";
import { QuickJoinCard } from "../../components/customer/QuickJoinCard";

export function ServiceDetailPage() {
  const { serviceId = "" } = useParams();
  const query = useQuery({
    queryKey: ["service", serviceId],
    queryFn: () => getService(serviceId),
  });

  return (
    <PageContainer className="py-10">
      {query.isLoading && <LoadingState label="Loading service..." />}
      {query.error instanceof Error && (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      )}
      {query.data && (
        <article className="rounded-2xl border border-ink/10 bg-white p-6">
          <p className="text-xs font-bold uppercase tracking-wide text-ink/50">{query.data.code}</p>
          <h1 className="mt-2 text-4xl font-black text-ink">{query.data.name}</h1>
          <p className="mt-4 text-ink/70">{query.data.description ?? "No description available."}</p>
          <p className="mt-4 text-sm text-ink/70">
            Average service time:{" "}
            <strong className="text-ink">{query.data.average_service_minutes} minutes</strong>
          </p>
          <Link to={`/join/${query.data.id}`} className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-white">
            Join queue
          </Link>
          <QuickJoinCard serviceId={query.data.id} branchId={query.data.branch_id} serviceName={query.data.name} />
        </article>
      )}
    </PageContainer>
  );
}
