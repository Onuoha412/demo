export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-white p-6 text-center text-ink/70">
      <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-ink/20 border-t-ink" />
      {label}
    </div>
  );
}
