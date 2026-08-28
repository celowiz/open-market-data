"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DatasetManifestCard } from "@/components/DatasetManifestCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchDatasets } from "@/lib/api";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function DatasetsPage() {
  const api = useApiStatus();
  const state = useClientFetch("datasets", () => fetchDatasets(), {
    enabled: api.status === "ok",
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Manifestos de conjuntos</h1>
        <p className="mt-1 text-sm text-slate-600">
          Listagens de <code className="font-mono text-xs">GET /v1/datasets</code>. Só entram
          catálogos com redistribuição permitida. Não há botão de download da B3.
        </p>
      </header>
      {api.status !== "unreachable" && (api.status === "loading" || state.status === "loading") ? (
        <LoadingState label="Carregando manifestos…" />
      ) : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <EmptyState>
          <p>Nenhum manifesto público foi publicado ainda.</p>
          <p className="mt-2 text-xs text-slate-500">
            Operadores: após um backfill ODbL, rode{" "}
            <code className="font-mono text-xs">marketdata publish datasets</code>.
          </p>
        </EmptyState>
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {state.data.map((dataset) => (
            <li key={`${dataset.dataset_name}-${dataset.snapshot_date}`}>
              <DatasetManifestCard
                dataset={dataset}
                detailHref={`/datasets/${encodeURIComponent(dataset.dataset_name)}`}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
