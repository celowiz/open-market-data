import type { ReactNode } from "react";

import { cn } from "@/lib/ui";

export function PageShell({
  children,
  className,
  wide = false,
}: {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col gap-6 px-4 py-6 sm:py-8",
        wide ? "max-w-7xl" : "max-w-6xl",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-1">
      {kicker ? (
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">{kicker}</p>
      ) : null}
      <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{title}</h1>
      {children ? <div className="max-w-3xl text-sm text-muted">{children}</div> : null}
    </header>
  );
}
