"use client";

import { Suspense, useEffect, useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AssetRow, AssetRowList } from "@/components/AssetRow";
import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PageHeader, PageShell } from "@/components/PageShell";
import { EmptyState, LoadingState, RowSkeleton } from "@/components/Status";
import { INSTRUMENT_PAGE_SIZE, fetchSources, listInstruments, searchInstruments } from "@/lib/api";
import { loadLatestPrint } from "@/lib/asset";
import { copy, offlineFormHint } from "@/lib/copy";
import { BRAZIL_HOME_EXAMPLES, type HomeExample } from "@/lib/examples";
import { hrefForInstrument } from "@/lib/links";
import { pickInstrumentMatch } from "@/lib/span";
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
      replaceFilters({ q: trimmed });
    }, 300);
    return () => window.clearTimeout(timer);
    // replaceFilters closes over current source/class
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput, qParam, source, assetClass, router]);

  const browsing = Boolean(qParam.trim() || source || assetClass);
  const applied = catalogQuery(source, assetClass, qParam.trim());
  const history = useHistoryPages({
    key: JSON.stringify(applied),
    enabled: apiReady && browsing,
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
          Busca em <span className="font-mono text-xs">GET /v1/instruments</span> com <span className="font-mono text-xs">q</span>.
          Sem consulta, mostramos exemplos — não uma busca vazia. Primeira e última cotação e o
          número de pregões vêm da API quando existem.
        </p>
      </PageHeader>

      <form
        className="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          replaceFilters({ q: qInput });
        }}
      >
        <div className="flex flex-col gap-1 sm:col-span-2 lg:col-span-1">
          <label htmlFor={queryId} className="text-sm font-medium text-foreground">
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
            className={fieldClass}
          />
        </div>
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

      {!browsing ? (
        <section className="flex flex-col gap-2" aria-labelledby="examples-heading">
          <h2 id="examples-heading" className="text-sm font-semibold text-foreground">
            {copy.common.examples}
          </h2>
          <p className="text-sm text-muted">{copy.common.curatedEmptySearch}</p>
          <AssetRowList label={copy.common.examples}>
            {BRAZIL_HOME_EXAMPLES.map((example) => (
              <li key={example.identifier}>
                <AtivosExampleRow example={example} />
              </li>
            ))}
          </AssetRowList>
        </section>
      ) : null}

      {browsing && api.status !== "unreachable" && history.status === "loading" ? (
        <RowSkeleton count={8} />
      ) : null}
      {browsing && history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {browsing && history.status === "success" && rows.length === 0 ? (
        <EmptyState>
          <p>Nenhum instrumento público corresponde a estes filtros.</p>
          <p className="mt-2 text-xs">{copy.common.historyLoading}</p>
        </EmptyState>
      ) : null}

      {browsing && rows.length > 0 ? (
        <>
          <AssetRowList label="Instrumentos">
            {rows.map((row) => (
              <li key={row.instrument_id}>
                <CatalogRow row={row} />
              </li>
            ))}
          </AssetRowList>
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

function CatalogRow({ row }: { row: InstrumentSearchItem }) {
  return (
    <AssetRow
      identifier={row.identifiers[0] ?? row.instrument_id}
      title={row.name}
      href={hrefForInstrument(row)}
      span={row}
    />
  );
}

function AtivosExampleRow({ example }: { example: HomeExample }) {
  const api = useApiStatus();
  const enabled = api.status === "ok";
  const latest = useClientFetch(
    `ativos-latest:${example.kind}:${example.identifier}`,
    () => loadLatestPrint(example),
    { enabled },
  );
  const catalog = useClientFetch(
    `ativos-span:${example.identifier}`,
    () => searchInstruments(example.identifier, 5),
    { enabled },
  );
  const match =
    catalog.status === "success"
      ? pickInstrumentMatch(catalog.data.instruments, example.identifier)
      : null;
  return (
    <AssetRow
      identifier={example.identifier}
      title={example.title}
      href={example.href}
      latest={latest.status === "success" ? latest.data : undefined}
      loading={latest.status === "loading"}
      span={match ?? undefined}
    />
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
