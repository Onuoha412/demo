import type { ComponentProps, ElementType, ReactNode } from "react";

type ButtonProps<T extends ElementType = "button"> = {
  as?: T;
  variant?: "primary" | "secondary";
  children: ReactNode;
} & Omit<ComponentProps<T>, "as" | "children">;

export function Button<T extends ElementType = "button">({ as, variant = "primary", className = "", children, ...props }: ButtonProps<T>) {
  const Component = as ?? "button";
  return <Component className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 ${variant === "primary" ? "bg-ink text-cream hover:bg-emerald-900" : "border border-ink/15 bg-transparent text-ink hover:bg-ink/5"} ${className}`} {...props}>{children}</Component>;
}
