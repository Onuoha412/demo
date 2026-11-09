import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import { getService, joinService } from "../../services/queue";
import { captureProductEvent } from "../../observability";

export function JoinQueuePage() {
  const { serviceId = "", branchId } = useParams();
  const [searchParams] = useSearchParams();
  const queueId = searchParams.get("queue_id") ?? undefined;
  const navigate = useNavigate();
  const [requestNote, setRequestNote] = useState("");
  const trackedServiceIdRef = useRef("");
  const service = useQuery({ queryKey: ["service", serviceId], queryFn: () => getService(serviceId), enabled: !!serviceId });
  useEffect(() => {
    if (service.data && trackedServiceIdRef.current !== service.data.id) {
      trackedServiceIdRef.current = service.data.id;
      captureProductEvent("service_selected");
    }
  }, [service.data]);
  const mutation = useMutation({
    mutationFn: () => joinService(serviceId, branchId, requestNote, queueId),
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
      <label className="mt-6 grid gap-2 text-sm font-semibold" htmlFor="queue-request-note">
        Request details (optional)
        <textarea
          id="queue-request-note"
          className="min-h-28 rounded-xl border border-ink/15 p-3 font-normal"
          maxLength={500}
          placeholder="Tell the service team what you need help with."
          value={requestNote}
          onChange={(event) => setRequestNote(event.target.value)}
        />
        <span className="text-right text-xs font-normal text-ink/50">
          {requestNote.length}/500
        </span>
      </label>
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
