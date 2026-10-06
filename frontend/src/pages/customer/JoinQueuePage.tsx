import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { getService, joinService } from "../../services/queue";

export function JoinQueuePage() {
  const { serviceId = "", branchId } = useParams();
  const navigate = useNavigate();
  const service = useQuery({ queryKey: ["service", serviceId], queryFn: () => getService(serviceId), enabled: !!serviceId });
  const mutation = useMutation({
    mutationFn: () => joinService(serviceId, branchId),
    onSuccess: (result) => navigate(`/queue/${result.id}`),
  });
  const branchMismatch = Boolean(branchId && service.data && service.data.branch_id !== branchId);

  return (
    <PageContainer className="max-w-2xl py-16">
      <h1 className="text-4xl font-black text-ink">{service.data ? `Join ${service.data.name}` : "Join queue"}</h1>
      {service.isLoading && <LoadingState label="Loading service..." />}
      {service.error instanceof Error && <ErrorState message={service.error.message} onRetry={() => void service.refetch()} />}
      {service.data && <p className="mt-2 text-sm text-ink/60">{service.data.description ?? "QueueLess service"}</p>}
      <p className="mt-3 text-ink/70">
        You are about to join this service queue. You will receive a queue number immediately.
      </p>
      {branchMismatch && <p className="mt-3 text-sm text-red-600">This service is not available at the selected branch.</p>}
      <button
        className="mt-8 rounded-full bg-ink px-6 py-3 text-white"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || branchMismatch || service.isLoading || service.isError || !service.data}
      >
        {mutation.isPending ? "Joining..." : "Confirm and join"}
      </button>
      {mutation.error instanceof Error && (
        <div className="mt-6">
          <ErrorState message={mutation.error.message} onRetry={() => mutation.mutate()} />
        </div>
      )}
    </PageContainer>
  );
}
