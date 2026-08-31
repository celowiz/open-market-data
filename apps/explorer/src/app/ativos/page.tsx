"use client";

import Link from "next/link";
import { Suspense, useEffect, useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { InstrumentSearch } from "@/components/InstrumentSearch";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PageHeader, PageShell } from "@/components/PageShell";
import { EmptyState, LoadingState, RowSkeleton } from "@/components/Status";
import { INSTRUMENT_PAGE_SIZE, fetchSources, listInstruments } from "@/lib/api";
import { copy, offlineFormHint } from "@/lib/copy";
import { hrefForInstrument } from "@/lib/links";
import { hasQuoteSpan } from "@/lib/span";
import type { InstrumentSearchItem, SourceResponse } from "@/lib/types";
import { fieldClass } from "@/lib/ui";
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

function AtivosPage() {
  const api = useApiStatus();
  const localOrigin = useLocalPageOrigin();
  const router = useRouter();
  const searchParams = useSearchParams();
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
      replaceFilters({ q: trimmed });
    }, 300);
    return () => window.clearTimeout(timer);
    // replaceFilters closes over current source/class
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput, qParam, source, assetClass, router]);

  const catalogFilters = Boolean(source || assetClass);
  const applied = catalogQuery(source, assetClass, qParam.trim());
  const history = useHistoryPages({
    key: JSON.stringify(applied),
    enabled: apiReady && catalogFilters,
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
    router.replace(qs ? `/ativos?${qs}` : "/ativos", { scroll: false });
  }

  const rows = history.items;

  return (
    <PageShell>
      <PageHeader kicker="Catálogo" title="Ativos">
        <p>
          Busca em <span className="font-mono text-xs">GET /v1/instruments</span> com{" "}
          <span className="font-mono text-xs">q</span>. Sem consulta, atalhos — a API exige q=. Primeira e
          última cotação e o número de pregões vêm da API quando existem.
        </p>
      </PageHeader>

      <InstrumentSearch variant="page" query={qInput} onQueryChange={setQInput} />

      <form
        className="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          replaceFilters({ q: qInput });
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor={sourceId} className="text-sm font-medium text-foreground">
            {copy.common.source}
          </label>
          <select
            id={sourceId}
            name="source"
            value={source}
            disabled={!apiReady}
            onChange={(event) => replaceFilters({ source: event.target.value })}
            className={fieldClass}
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
          <label htmlFor={classId} className="text-sm font-medium text-foreground">
            Classe
          </label>
          <select
            id={classId}
            name="asset_class"
            value={assetClass}
            disabled={!apiReady}
            onChange={(event) => replaceFilters({ asset_class: event.target.value })}
            className={fieldClass}
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
        <p className="text-sm text-muted">{offlineFormHint(localOrigin)}</p>
      ) : null}

      {catalogFilters && api.status !== "unreachable" && history.status === "loading" ? (
        <RowSkeleton count={8} />
      ) : null}
      {catalogFilters && history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {catalogFilters && history.status === "success" && rows.length === 0 ? (
        <EmptyState>
          <p>Nenhum instrumento público corresponde a estes filtros.</p>
          <p className="mt-2 text-xs">{copy.common.historyLoading}</p>
        </EmptyState>
      ) : null}

      {catalogFilters && rows.length > 0 ? (
        <>
          <ul aria-label="Instrumentos" className="grid gap-3">
            {rows.map((row) => (
              <li key={row.instrument_id}>
                <CatalogCard row={row} />
              </li>
            ))}
          </ul>
          <LoadMoreButton
            hasMore={history.hasMore}
            loading={history.loadingMore}
            onClick={history.loadMore}
          />
        </>
      ) : null}
    </PageShell>
  );
}

function CatalogCard({ row }: { row: InstrumentSearchItem }) {
  const identifier = row.identifiers[0] ?? row.instrument_id;
  const extraIds = row.identifiers.filter((id) => id !== identifier).slice(0, 5);
  return (
    <Link
      href={hrefForInstrument(row)}
      className="block rounded-2xl border border-border bg-surface px-4 py-3 hover:bg-elevated/80"
    >
      <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="break-all font-mono text-sm text-foreground">{identifier}</p>
          {row.name && row.name !== identifier ? (
            <p className="text-sm text-muted">{row.name}</p>
          ) : null}
          {extraIds.length > 0 ? (
            <p className="mt-1 font-mono text-[11px] text-muted">{extraIds.join(", ")}</p>
          ) : null}
        </div>
        {hasQuoteSpan(row) ? (
          <dl className="flex min-w-0 flex-col gap-1 font-mono text-[11px] text-muted sm:items-end">
            {row.first_quote_date ? (
              <div>
                <dt className="inline">{copy.common.firstQuote}: </dt>
                <dd className="inline">{row.first_quote_date}</dd>
              </div>
            ) : null}
            {row.last_quote_date ? (
              <div>
                <dt className="inline">{copy.common.lastQuote}: </dt>
                <dd className="inline">{row.last_quote_date}</dd>
              </div>
            ) : null}
            {row.quote_count != null ? (
              <div>
                <dt className="inline">{copy.common.sessions}: </dt>
                <dd className="inline">{row.quote_count.toLocaleString("pt-BR")}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
      </div>
    </Link>
  );
}

export default function AtivosRoute() {
  return (
    <Suspense
      fallback={
        <PageShell>
          <LoadingState label="Carregando catálogo de ativos…" />
        </PageShell>
      }
    >
      <AtivosPage />
    </Suspense>
  );
}
