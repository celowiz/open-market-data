"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { fetchLending, isNotFoundError } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatDisplayValue } from "@/lib/format-display-value";
import { hasLendingData, latestLendingSnapshot } from "@/lib/lending";
import { useClientFetch } from "@/lib/use-client-fetch";
import type { LendingResponse } from "@/lib/types";

export function LendingPanel({ identifier }: { identifier: string }) {
  const api = useApiStatus();
  const enabled = api.status === "ok" && Boolean(identifier);
  const state = useClientFetch<LendingResponse | null>(
    `lending:${identifier}`,
    async () => {
      try {
        return await fetchLending(identifier);
      } catch (error) {
        if (isNotFoundError(error)) {
          return null;
        }
        throw error;
      }
    },
    { enabled },
  );

  if (!enabled || state.status === "loading") {
    return null;
  }
  if (state.status === "error") {
    return null;
  }
  const snapshots = state.data?.snapshots ?? [];
  if (!hasLendingData(snapshots)) {
    return null;
  }
  const open = latestLendingSnapshot(snapshots, "open_position");
  const registered = latestLendingSnapshot(snapshots, "registered");

  return (
    <section
      aria-label={copy.lending.title}
      className="rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-foreground"
    >
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {copy.lending.title}
      </h2>
      <dl className="grid gap-3 sm:grid-cols-2">
        <LendingBlock
          title={copy.lending.open}
          qty={open?.qty ?? null}
          rate={open?.avg_rate ?? null}
          contracts={open?.contracts ?? null}
          date={open?.date}
        />
        <LendingBlock
          title={copy.lending.registered}
          qty={registered?.qty ?? null}
          rate={registered?.avg_rate ?? null}
          contracts={registered?.contracts ?? null}
          date={registered?.date}
        />
      </dl>
    </section>
  );
}

function LendingBlock({
  title,
  qty,
  rate,
  contracts,
  date,
}: {
  title: string;
  qty: string | null;
  rate: string | null;
  contracts: number | null;
  date?: string;
}) {
  return (
    <div className="rounded-xl border border-border/80 bg-elevated/40 px-3 py-2">
      <dt className="text-xs text-muted">
        {title}
        {date ? ` · ${date}` : ""}
      </dt>
      <dd className="mt-1 grid grid-cols-3 gap-2 font-mono text-xs sm:text-sm">
        <span>
          <span className="block text-[10px] uppercase tracking-wide text-muted">{copy.lending.qty}</span>
          {formatDisplayValue(qty)}
        </span>
        <span>
          <span className="block text-[10px] uppercase tracking-wide text-muted">{copy.lending.rate}</span>
          {formatDisplayValue(rate)}
        </span>
        <span>
          <span className="block text-[10px] uppercase tracking-wide text-muted">
            {copy.lending.contracts}
          </span>
          {contracts ?? "—"}
        </span>
      </dd>
    </div>
  );
}
