"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { OfflineState } from "@/components/OfflineState";
import { EmptyState, LoadingState } from "@/components/Status";
import { SourcesTable } from "@/components/SourcesTable";
import { fetchSources } from "@/lib/api";
import { copy } from "@/lib/copy";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function SourcesPage() {
  const api = useApiStatus();
  const state = useClientFetch("sources", () => fetchSources(), {
    enabled: api.status === "ok",
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Fontes</h1>
        <p className="mt-1 text-sm text-slate-600">
          Fontes visíveis na API pública, de{" "}
          <code className="font-mono text-xs">GET /v1/sources</code>. A lista inclui toda fonte com
          API pública habilitada.
        </p>
      </header>
      {api.status === "unreachable" ? <OfflineState /> : null}
      {api.status !== "unreachable" && (api.status === "loading" || state.status === "loading") ? (
        <LoadingState label="Carregando fontes…" />
      ) : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <EmptyState>
          <p>A API devolveu uma lista de fontes vazia.</p>
          <p className="mt-2 text-xs text-slate-500">{copy.common.backfillSecondary}</p>
        </EmptyState>
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <SourcesTable sources={state.data} />
      ) : null}
    </div>
  );
}
