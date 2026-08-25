"use client";

import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchDatasets } from "@/lib/api";
import { isBlockedDatasetDownload } from "@/lib/links";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function DatasetsPage() {
  const state = useClientFetch("datasets", () => fetchDatasets());

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Dataset manifests</h1>
        <p className="mt-1 text-sm text-slate-600">
          Listings from <code className="font-mono text-xs">GET /v1/datasets</code>. Only
          redistribution-allowlisted catalogs appear. There is no B3 download button.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState label="Loading manifests…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <EmptyState>
          <p>No public dataset manifests are published yet.</p>
          <p className="mt-2">
            After an ODbL backfill, operators can run{" "}
            <code className="font-mono text-xs">marketdata publish datasets</code>.
          </p>
        </EmptyState>
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {state.data.map((dataset) => {
            const blocked = isBlockedDatasetDownload(dataset.sources, dataset.dataset_name);
            const fileUrl = !blocked && dataset.url ? dataset.url : null;
            return (
              <li
                key={`${dataset.dataset_name}-${dataset.snapshot_date}`}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <h2 className="text-lg font-semibold text-slate-900">{dataset.dataset_name}</h2>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-slate-500">Schema</dt>
                    <dd className="font-mono">{dataset.schema_version}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Snapshot date</dt>
                    <dd className="font-mono">{dataset.snapshot_date}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Generated at</dt>
                    <dd className="font-mono text-xs">{dataset.generated_at}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Rows</dt>
                    <dd>{dataset.row_count}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">License</dt>
                    <dd>{dataset.license}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Redistribution</dt>
                    <dd className="font-mono text-xs">{dataset.redistribution_policy}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-slate-500">Sources</dt>
                    <dd>{dataset.sources.join(", ") || "—"}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-slate-500">Object key</dt>
                    <dd className="break-all font-mono text-xs">{dataset.object_key}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-slate-500">SHA-256</dt>
                    <dd className="break-all font-mono text-xs">{dataset.sha256}</dd>
                  </div>
                </dl>
                <div className="mt-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Attribution
                  </h3>
                  {dataset.attribution.length === 0 ? (
                    <p className="text-sm text-slate-600">No attribution lines on this manifest.</p>
                  ) : (
                    <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                      {dataset.attribution.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  )}
                </div>
                {fileUrl ? (
                  <p className="mt-3 text-sm">
                    <a
                      href={fileUrl}
                      rel="nofollow noopener noreferrer"
                      target="_blank"
                      className="font-medium text-teal-800 hover:underline"
                    >
                      Dataset file
                    </a>
                  </p>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">
                    {blocked
                      ? "No download is offered for blocked sources (including B3)."
                      : "No public file URL is configured for this manifest."}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
