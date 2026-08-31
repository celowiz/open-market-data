"use client";

import Link from "next/link";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { fetchCoverageSpan, formatApiError, isNotFoundError, isTimeoutError } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatPregoes } from "@/lib/span";
import { useClientFetch } from "@/lib/use-client-fetch";

export function CoverageSpanChip() {
  const api = useApiStatus();
  const span = useClientFetch("coverage-span:scratch", () => fetchCoverageSpan({ universe: "scratch" }), {
    enabled: api.status === "ok",
  });

  if (api.status === "unreachable") {
    return null;
  }
  if (span.status === "loading") {
    return <div className="skeleton h-8 w-full rounded-full" aria-hidden="true" />;
  }
  if (span.status === "error") {
    if (isNotFoundError(span.error) || isTimeoutError(span.error)) {
      return (
        <p className="rounded-full border border-border px-3 py-1 text-[11px] text-muted">
          {copy.common.historyLoading}
        </p>
      );
    }
    return (
      <p className="truncate text-[11px] text-danger" title={formatApiError(span.error)}>
        {formatApiError(span.error)}
      </p>
    );
  }

  const data = span.data;
  return (
    <Link
      href="/coverage"
      className="inline-flex max-w-full items-center gap-2 truncate rounded-full border border-border px-3 py-1 text-[11px] text-muted transition-colors hover:border-accent/40 hover:text-foreground"
    >
      <span className="size-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
      <span className="truncate">
        scratch {data.instruments_with_quotes}/{data.universe_size}
        {data.min_date && data.max_date ? ` · ${data.min_date} → ${data.max_date}` : ""}
        {` · ${formatPregoes(data.quote_count)}`}
      </span>
    </Link>
  );
}
