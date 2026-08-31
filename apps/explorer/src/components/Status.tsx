import type { ReactNode } from "react";

import { copy } from "@/lib/copy";

export function LoadingState({ label = copy.common.loading }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-muted">
      {label}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-6 text-sm text-muted">
      {children}
    </div>
  );
}

export function SkeletonBlock({ label = copy.common.loading }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <span className="sr-only">{label}</span>
      <div className="skeleton h-7 w-24 rounded" />
      <div className="skeleton h-3 w-40 rounded" />
    </div>
  );
}

export function ChartSkeleton({ label = copy.common.loading }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex h-[260px] flex-col justify-end gap-3 sm:h-[24rem]">
      <span className="sr-only">{label}</span>
      <div className="skeleton h-full w-full rounded-2xl" />
    </div>
  );
}

export function RowSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <span className="sr-only">{copy.common.loading}</span>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex items-center justify-between rounded-xl px-3 py-2.5">
          <div className="flex flex-col gap-1">
            <div className="skeleton h-4 w-20 rounded" />
            <div className="skeleton h-3 w-28 rounded" />
          </div>
          <div className="skeleton h-4 w-14 rounded" />
        </div>
      ))}
    </div>
  );
}
