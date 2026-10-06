export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-2 text-sm">{message}</p>
      {onRetry && (
        <button
          className="mt-4 rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white"
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  );
}
