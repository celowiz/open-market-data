import type { ReactNode } from "react";

import { copy } from "@/lib/copy";

export function LoadingState({ label = copy.common.loading }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-slate-600">
      {label}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-700">
      {children}
    </div>
  );
}

export function SkeletonBlock({ label = copy.common.loading }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2">
      <span className="sr-only">{label}</span>
      <div className="h-7 w-24 animate-pulse rounded bg-slate-200" />
      <div className="h-3 w-40 animate-pulse rounded bg-slate-200" />
    </div>
  );
}
