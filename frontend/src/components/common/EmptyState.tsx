import type { ReactNode } from "react";

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-white p-6 text-center">
      <p className="font-bold text-ink">{title}</p>
      <p className="mt-2 text-sm text-ink/60">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
