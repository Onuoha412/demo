export function WaitTimeCard({
  estimatedWaitMinutes,
  refreshedAt,
  prediction,
}: {
  estimatedWaitMinutes: number;
  refreshedAt: number;
  prediction?: {
    estimated_minutes: number;
    lower_bound_minutes: number;
    upper_bound_minutes: number;
    factors: { explanation: string };
  };
}) {
  return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900">
      <p className="text-xs uppercase tracking-wide">Predictive/statistical estimation</p>
      <p className="mt-2 text-xs uppercase tracking-wide">Estimated wait</p>
      <p className="mt-2 text-3xl font-black">{prediction?.estimated_minutes ?? estimatedWaitMinutes} min</p>
      {prediction && <p className="mt-1 text-sm">Range: {prediction.lower_bound_minutes}-{prediction.upper_bound_minutes} min</p>}
      {prediction && <p className="mt-2 text-xs">{prediction.factors.explanation}</p>}
      <p className="mt-2 text-xs">
        {refreshedAt
          ? `Last updated ${new Date(refreshedAt).toLocaleTimeString()}`
          : "Updating estimate..."}
      </p>
    </div>
  );
}
