"use client";

import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState, LoadingState } from "@/components/Status";
import { SourcesTable } from "@/components/SourcesTable";
import { fetchSources } from "@/lib/api";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function SourcesPage() {
  const state = useClientFetch("sources", () => fetchSources());

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Sources</h1>
        <p className="mt-1 text-sm text-slate-600">
          Public-API-visible sources from <code className="font-mono text-xs">GET /v1/sources</code>
          . The list includes every source with public API enabled.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState label="Loading sources…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <EmptyState>
          <p>The API returned an empty source list.</p>
          <p className="mt-2">Run backfill after providers are registered, then refresh.</p>
        </EmptyState>
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <SourcesTable sources={state.data} />
      ) : null}
    </div>
  );
}
