"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { DateRangeForm } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ObservationsTable } from "@/components/ObservationsTable";
import { PriceChart } from "@/components/PriceChart";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchSeriesObservations } from "@/lib/api";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import { useClientFetch } from "@/lib/use-client-fetch";

function SeriesPage() {
  const params = useParams<{ code: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const code = routeParam(params.code);
  const defaults = useMemo(() => defaultHistoryRange(5), []);

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
  });

  const key = JSON.stringify({ code, ...applied });
  const state = useClientFetch(key, () =>
    fetchSeriesObservations(code, { start: applied.start, end: applied.end }),
  );

  function applyFilters() {
    setApplied({ start, end });
    const qs = new URLSearchParams();
    if (start) qs.set("start", start);
    if (end) qs.set("end", end);
    router.replace(`/series/${encodeURIComponent(code)}?${qs.toString()}`);
  }

  const observations = state.status === "success" ? state.data.observations : [];
  const unit = state.status === "success" ? state.data.unit : "";

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <p className="text-sm text-slate-500">Market series</p>
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{code || "—"}</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/series/{"{code}"}/observations</code>
          {unit ? (
            <>
              {" "}
              · unit <span className="font-mono">{unit}</span>
            </>
          ) : null}
        </p>
      </header>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
      />

      {state.status === "loading" ? <LoadingState label="Loading observations…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}

      {state.status === "success" ? (
        <>
          <ProvenanceStrip
            items={observations.map((row) => ({
              source: row.source,
              unit: row.unit,
              revision: row.revision,
            }))}
            extra={
              <p className="mt-2 text-sm">
                Series unit: <span className="font-mono">{state.data.unit}</span>
              </p>
            }
          />
          {observations.length === 0 ? (
            <EmptyState>
              <p>No observations in this window.</p>
              <p className="mt-2">
                Empty API results are shown as empty — values are never fabricated. Run{" "}
                <code className="font-mono text-xs">marketdata backfill bcb</code> if you expected
                CDI / SELIC / PTAX history.
              </p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                label={state.data.unit || "Value"}
                rows={observations.map((row) => ({ date: row.date, raw: row.value }))}
              />
              <ObservationsTable observations={observations} />
              {state.data.next_cursor ? (
                <p className="text-sm text-slate-600">
                  More rows exist before{" "}
                  <span className="font-mono">{state.data.next_cursor}</span> (limit 5000).
                </p>
              ) : null}
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
          <LoadingState label="Loading series page…" />
        </div>
      }
    >
      <SeriesPage />
    </Suspense>
  );
}
