"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { DateRangeForm } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PriceChart } from "@/components/PriceChart";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { QuotesTable } from "@/components/QuotesTable";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchFundQuotes } from "@/lib/api";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import { useClientFetch } from "@/lib/use-client-fetch";

function FundQuotesPage() {
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const identifier = routeParam(params.identifier);
  const defaults = useMemo(() => defaultHistoryRange(5), []);

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
  });

  const key = JSON.stringify({ identifier, ...applied });
  const state = useClientFetch(key, () =>
    fetchFundQuotes(identifier, { start: applied.start, end: applied.end }),
  );

  function applyFilters() {
    setApplied({ start, end });
    const qs = new URLSearchParams();
    if (start) qs.set("start", start);
    if (end) qs.set("end", end);
    router.replace(`/funds/${encodeURIComponent(identifier)}?${qs.toString()}`);
  }

  const quotes = state.status === "success" ? state.data.quotes : [];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <p className="text-sm text-slate-500">Fund quotes</p>
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{identifier || "—"}</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/funds/{"{identifier}"}/quotes</code>
        </p>
      </header>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
      />

      {state.status === "loading" ? <LoadingState label="Loading fund quotes…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}

      {state.status === "success" ? (
        <>
          <ProvenanceStrip items={quotes} />
          {quotes.length === 0 ? (
            <EmptyState>
              <p>No fund quotes in this window.</p>
              <p className="mt-2">
                Missing NAV is not replaced with a placeholder. Run{" "}
                <code className="font-mono text-xs">marketdata backfill cvm</code> if you expected
                history for this CNPJ.
              </p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                label="NAV"
                rows={quotes.map((quote) => ({ date: quote.date, raw: quote.price }))}
              />
              <QuotesTable quotes={quotes} />
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

export default function FundQuotesRoute() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Loading fund page…" />
        </div>
      }
    >
      <FundQuotesPage />
    </Suspense>
  );
}
