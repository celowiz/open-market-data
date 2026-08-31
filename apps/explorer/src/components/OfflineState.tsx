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
    return <p className="text-sm text-muted">{message}</p>;
  }
  return (
    <div className="rounded-2xl border border-dashed border-border bg-elevated px-4 py-6 text-sm text-foreground">
      <p>{message}</p>
    </div>
  );
}
