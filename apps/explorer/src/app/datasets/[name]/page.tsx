"use client";

import { useParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DatasetManifestCard } from "@/components/DatasetManifestCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingState } from "@/components/Status";
import { fetchDataset } from "@/lib/api";
import { routeParam } from "@/lib/dates";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function DatasetDetailPage() {
  const params = useParams<{ name: string }>();
  const name = routeParam(params.name);
  const api = useApiStatus();
  const state = useClientFetch(`dataset:${name}`, () => fetchDataset(name), {
    enabled: api.status === "ok" && Boolean(name),
  });

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:py-8">
      <header>
        <p className="text-sm text-muted">Conjunto de dados</p>
        <h1 className="font-mono text-2xl font-semibold text-foreground">{name || "—"}</h1>
        <p className="mt-1 text-sm text-muted">
          <code className="font-mono text-xs">GET /v1/datasets/{"{name}"}</code>
        </p>
      </header>
      {api.status !== "unreachable" && (api.status === "loading" || state.status === "loading") ? (
        <LoadingState label="Carregando manifesto…" />
      ) : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}
      {state.status === "success" ? <DatasetManifestCard dataset={state.data} /> : null}
    </div>
  );
}
