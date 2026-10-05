import type { HTMLAttributes } from "react";

export function PageContainer({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`mx-auto w-full max-w-7xl px-6 lg:px-10 ${className}`} {...props} />;
}
