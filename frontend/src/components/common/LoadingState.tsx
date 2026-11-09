export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div
      className="rounded-2xl border border-ink/10 bg-white p-8 text-center text-ink/70"
      role="progressbar"
      aria-label={label}
      aria-live="polite"
    >
      <div className="mx-auto mb-3 h-7 w-7 animate-spin rounded-full border-2 border-ink/20 border-t-ink" aria-hidden="true" />
      {label}
    </div>
  );
}
