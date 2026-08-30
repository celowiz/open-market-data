"use client";

import Link from "next/link";
import { Suspense, useEffect, useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { EmptyState, LoadingState } from "@/components/Status";
import { INSTRUMENT_PAGE_SIZE, fetchSources, listInstruments } from "@/lib/api";
import { copy, offlineFormHint } from "@/lib/copy";
import { hrefForInstrument } from "@/lib/links";
import type { InstrumentSearchItem, SourceResponse } from "@/lib/types";
import { useClientFetch } from "@/lib/use-client-fetch";
import { useHistoryPages } from "@/lib/use-history-pages";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

const ASSET_CLASSES = [
  "equity",
  "fund",
  "government_bond",
  "future",
  "option",
  "fx",
  "rate",
  "credit",
  "other",
] as const;

function catalogQuery(source: string, assetClass: string, q: string) {
  return {
    q: q || undefined,
    source: source || undefined,
    asset_class: assetClass || undefined,
  };
}

function InstrumentsTable({ rows }: { rows: InstrumentSearchItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Instrumentos públicos</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Nome
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Identificadores
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Classe
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Fonte
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.instrument_id} className="border-t border-slate-100">
              <td className="px-3 py-2">
                <Link
                  href={hrefForInstrument(row)}
                  className="font-medium text-teal-800 hover:underline"
                >
                  {row.name}
                </Link>
              </td>
              <td className="px-3 py-2 font-mono text-xs text-slate-700">
                {row.identifiers.length > 0 ? row.identifiers.slice(0, 6).join(", ") : "—"}
              </td>
              <td className="px-3 py-2">{row.asset_class}</td>
              <td className="px-3 py-2">
                {row.sources && row.sources.length > 0 ? row.sources.join(", ") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InstrumentsCatalogPage() {
  const api = useApiStatus();
  const localOrigin = useLocalPageOrigin();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryId = useId();
  const sourceId = useId();
  const classId = useId();
  const apiReady = api.status === "ok";

  const source = searchParams.get("source") ?? "";
  const assetClass = searchParams.get("asset_class") ?? "";
  const qParam = searchParams.get("q") ?? "";
  const [qInput, setQInput] = useState(qParam);
  const [prevQParam, setPrevQParam] = useState(qParam);
  if (qParam !== prevQParam) {
    setPrevQParam(qParam);
    setQInput(qParam);
  }

  useEffect(() => {
    const trimmed = qInput.trim();
    if (trimmed === qParam) {
      return;
    }
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (trimmed) {
        params.set("q", trimmed);
      }
      if (source) {
        params.set("source", source);
      }
      if (assetClass) {
        params.set("asset_class", assetClass);
      }
      const qs = params.toString();
      router.replace(qs ? `/instruments?${qs}` : "/instruments", { scroll: false });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [assetClass, qInput, qParam, router, source]);

  const applied = catalogQuery(source, assetClass, qParam.trim());
  const history = useHistoryPages({
    key: JSON.stringify(applied),
    enabled: apiReady,
    fetchPage: (cursor, signal) =>
      listInstruments({ ...applied, limit: INSTRUMENT_PAGE_SIZE, cursor }, signal),
    itemsOf: (page) => page.instruments,
    cursorOf: (page) => page.next_cursor ?? null,
  });
  const sources = useClientFetch("sources", () => fetchSources(), {
    enabled: apiReady,
  });
  const sourceOptions: SourceResponse[] = sources.status === "success" ? sources.data : [];

  function replaceFilters(next: { source?: string; asset_class?: string; q?: string }) {
    const params = new URLSearchParams();
    const nextQ = (next.q ?? qInput).trim();
    const nextSource = next.source ?? source;
    const nextClass = next.asset_class ?? assetClass;
    if (nextQ) {
      params.set("q", nextQ);
    }
    if (nextSource) {
      params.set("source", nextSource);
    }
    if (nextClass) {
      params.set("asset_class", nextClass);
    }
    const qs = params.toString();
    router.replace(qs ? `/instruments?${qs}` : "/instruments", { scroll: false });
  }

  const rows = history.items;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Ativos</h1>
        <p className="mt-1 text-sm text-slate-600">
          Catálogo de <code className="font-mono text-xs">GET /v1/instruments</code>. Sem consulta,
          a API lista os instrumentos públicos (com cotação de fonte habilitada), paginados. Séries
          BCB continuam em{" "}
          <Link href="/series" className="font-medium text-teal-800 hover:underline">
            Séries
          </Link>
          .
        </p>
      </header>

      <form
        className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          replaceFilters({ q: qInput });
        }}
      >
        <div className="flex flex-col gap-1 sm:col-span-2 lg:col-span-1">
          <label htmlFor={queryId} className="text-sm font-medium text-slate-800">
            Busca
          </label>
          <input
            id={queryId}
            name="q"
            type="search"
            autoComplete="off"
            placeholder="Nome ou identificador"
            value={qInput}
            disabled={!apiReady}
            onChange={(event) => setQInput(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={sourceId} className="text-sm font-medium text-slate-800">
            {copy.common.source}
          </label>
          <select
            id={sourceId}
            name="source"
            value={source}
            disabled={!apiReady}
            onChange={(event) => replaceFilters({ source: event.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          >
            <option value="">Todas as fontes</option>
            {sourceOptions.map((item) => (
              <option key={item.name} value={item.name}>
                {item.display_name} ({item.name})
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={classId} className="text-sm font-medium text-slate-800">
            Classe
          </label>
          <select
            id={classId}
            name="asset_class"
            value={assetClass}
            disabled={!apiReady}
            onChange={(event) => replaceFilters({ asset_class: event.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          >
            <option value="">Todas as classes</option>
            {ASSET_CLASSES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      </form>
      {!apiReady && api.status === "unreachable" ? (
        <p className="text-sm text-slate-600">{offlineFormHint(localOrigin)}</p>
      ) : null}

      {api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando ativos…" />
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {history.status === "success" && rows.length === 0 ? (
        <EmptyState>
          <p>Nenhum instrumento público corresponde a estes filtros.</p>
          <p className="mt-2 text-xs text-slate-500">{copy.common.backfillSecondary}</p>
        </EmptyState>
      ) : null}

      {rows.length > 0 ? (
        <>
          <InstrumentsTable rows={rows} />
          <LoadMoreButton
            hasMore={history.hasMore}
            loading={history.loadingMore}
            onClick={history.loadMore}
          />
        </>
      ) : null}
    </div>
  );
}

export default function InstrumentsRoute() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Carregando catálogo de ativos…" />
        </div>
      }
    >
      <InstrumentsCatalogPage />
    </Suspense>
  );
}
