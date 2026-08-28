"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DateRangeForm, type DateRangeValue } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LatestHeadline } from "@/components/LatestHeadline";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { ObservationsTable } from "@/components/ObservationsTable";
import { OfflineState } from "@/components/OfflineState";
import { PriceChart } from "@/components/PriceChart";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchSeriesObservations } from "@/lib/api";
import { copy } from "@/lib/copy";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import { useHistoryPages } from "@/lib/use-history-pages";

function SeriesPage() {
  const params = useParams<{ code: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const api = useApiStatus();
  const code = routeParam(params.code);
  const defaults = useMemo(() => defaultHistoryRange(5), []);
  const apiReady = api.status === "ok";

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
  });

  const key = JSON.stringify({ code, ...applied });
  const history = useHistoryPages({
    key,
    enabled: apiReady && Boolean(code),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        code,
        {
          start: applied.start || undefined,
          end: applied.end || undefined,
          cursor,
        },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });

  function applyFilters(range?: DateRangeValue) {
    const next = { start: range?.start ?? start, end: range?.end ?? end };
    setStart(next.start);
    setEnd(next.end);
    setApplied(next);
    const qs = new URLSearchParams();
    if (next.start) qs.set("start", next.start);
    if (next.end) qs.set("end", next.end);
    router.replace(`/series/${encodeURIComponent(code)}?${qs.toString()}`);
  }

  const observations = history.items;
  const unit = history.firstPage?.unit ?? observations[0]?.unit ?? "";

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <p className="text-sm text-slate-500">Série de mercado</p>
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{code || "—"}</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/series/{"{code}"}/observations</code>
          {unit ? (
            <>
              {" "}
              · unidade <span className="font-mono">{unit}</span>
            </>
          ) : null}
        </p>
        <LatestHeadline kind="series" identifier={code} />
      </header>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
        disabled={!apiReady}
        disabledHint={copy.offline.formHint}
      />

      {api.status === "unreachable" ? <OfflineState /> : null}
      {api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando observações…" />
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {history.status === "success" ? (
        <>
          <ProvenanceStrip
            items={observations.map((row) => ({
              source: row.source,
              unit: row.unit,
              revision: row.revision,
            }))}
            extra={
              <p className="mt-2 text-sm">
                Unidade da série: <span className="font-mono">{unit}</span>
              </p>
            }
          />
          {observations.length === 0 ? (
            <EmptyState>
              <p>Nenhuma observação neste intervalo.</p>
              <p className="mt-2 text-xs text-slate-500">
                Operadores: rode <code className="font-mono">marketdata backfill bcb</code> se
                esperava histórico de CDI / SELIC / PTAX.
              </p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                label={unit || "Valor"}
                rows={observations.map((row) => ({ date: row.date, raw: row.value }))}
              />
              <ObservationsTable observations={observations} />
              <LoadMoreButton
                hasMore={history.hasMore}
                loading={history.loadingMore}
                onClick={history.loadMore}
              />
            </>
          )}
        </>
      ) : null}
    </div>
  );
}

export default function SeriesRoute() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Carregando página da série…" />
        </div>
      }
    >
      <SeriesPage />
    </Suspense>
  );
}
