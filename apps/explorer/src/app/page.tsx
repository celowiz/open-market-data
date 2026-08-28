"use client";

import Link from "next/link";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ExampleCards } from "@/components/ExampleCards";
import { InstrumentSearch } from "@/components/InstrumentSearch";
import { OfflineState } from "@/components/OfflineState";
import { EmptyState, LoadingState } from "@/components/Status";
import { SourcesTable } from "@/components/SourcesTable";
import { fetchSources } from "@/lib/api";
import { copy } from "@/lib/copy";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function HomePage() {
  const api = useApiStatus();
  const sources = useClientFetch("sources", () => fetchSources(), {
    enabled: api.status === "ok",
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-8">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Explorador de dados de mercado públicos
        </h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Consulte cotações, séries, fundos, cobertura e manifestos de conjuntos de dados
          publicados pela API FastAPI /v1. Este aplicativo não se conecta ao PostgreSQL, à CVM
          nem à B3 diretamente.
        </p>
      </section>

      <InstrumentSearch />

      <section aria-labelledby="examples-heading" className="flex flex-col gap-3">
        <h2 id="examples-heading" className="text-xl font-semibold text-slate-900">
          Identificadores de exemplo
        </h2>
        <p className="text-sm text-slate-600">
          Cada cartão consulta a API ao vivo. Um 404 mostra o corpo do erro — nunca um preço
          inventado.
        </p>
        <ExampleCards />
      </section>

      <section aria-labelledby="sources-heading" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="sources-heading" className="text-xl font-semibold text-slate-900">
            Fontes públicas
          </h2>
          <Link href="/sources" className="text-sm font-medium text-teal-800 hover:underline">
            Tabela completa de fontes
          </Link>
        </div>
        <p className="text-sm text-slate-600">
          De <code className="font-mono text-xs">GET /v1/sources</code>. Aparecem as fontes com API
          pública habilitada, inclusive Yahoo.
        </p>
        {api.status === "unreachable" ? <OfflineState /> : null}
        {api.status !== "unreachable" &&
        (api.status === "loading" || sources.status === "loading") ? (
          <LoadingState label="Carregando fontes…" />
        ) : null}
        {sources.status === "error" ? <ErrorBanner error={sources.error} /> : null}
        {sources.status === "success" && sources.data.length === 0 ? (
          <EmptyState>
            <p>Nenhuma fonte pública está visível ainda.</p>
            <p className="mt-2 text-xs text-slate-500">{copy.common.backfillSecondary}</p>
          </EmptyState>
        ) : null}
        {sources.status === "success" && sources.data.length > 0 ? (
          <SourcesTable sources={sources.data} />
        ) : null}
      </section>

      <section aria-labelledby="datasets-heading" className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 id="datasets-heading" className="text-xl font-semibold text-slate-900">
          Conjuntos de dados
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Manifestos Parquet públicos (ODbL / atribuição) ficam na página de{" "}
          <Link href="/datasets" className="font-medium text-teal-800 hover:underline">
            conjuntos de dados
          </Link>
          . Arquivos da B3 não são oferecidos para download.
        </p>
      </section>
    </div>
  );
}
