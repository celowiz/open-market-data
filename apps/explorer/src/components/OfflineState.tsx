"use client";

import { getApiBaseUrl } from "@/lib/api";
import { offlineBannerMessage, offlineCompactMessage } from "@/lib/copy";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

export function OfflineState({ compact = false }: { compact?: boolean }) {
  const local = useLocalPageOrigin();
  const message = compact
    ? offlineCompactMessage(local)
    : offlineBannerMessage(local, getApiBaseUrl());
  if (compact) {
    return <p className="text-sm text-slate-600">{message}</p>;
  }
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-700">
      <p>{message}</p>
    </div>
  );
}
