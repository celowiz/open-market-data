"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { DateRangeForm } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PriceChart } from "@/components/PriceChart";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { QuotesTable } from "@/components/QuotesTable";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchQuoteHistory } from "@/lib/api";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import { useClientFetch } from "@/lib/use-client-fetch";

function QuoteHistoryPage() {
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const identifier = routeParam(params.identifier);
  const defaults = useMemo(() => defaultHistoryRange(5), []);

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [priceType, setPriceType] = useState(searchParams.get("price_type") ?? "");
  const [source, setSource] = useState(searchParams.get("source") ?? "");
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
    price_type: searchParams.get("price_type") ?? "",
    source: searchParams.get("source") ?? "",
  });

  const key = JSON.stringify({ identifier, ...applied });
  const state = useClientFetch(key, () =>
    fetchQuoteHistory(identifier, {
      start: applied.start,
      end: applied.end,
      price_type: applied.price_type || undefined,
      source: applied.source || undefined,
    }),
  );

  function applyFilters() {
    const next = { start, end, price_type: priceType, source };
    setApplied(next);
    const qs = new URLSearchParams();
    if (start) qs.set("start", start);
    if (end) qs.set("end", end);
    if (priceType.trim()) qs.set("price_type", priceType.trim());
    if (source.trim()) qs.set("source", source.trim());
    router.replace(`/quotes/${encodeURIComponent(identifier)}?${qs.toString()}`);
  }

  const quotes = state.status === "success" ? state.data.quotes : [];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <p className="text-sm text-slate-500">Instrument quotes</p>
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{identifier || "—"}</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/quotes/{"{identifier}"}/history</code>
        </p>
      </header>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
        extra={
          <>
            <div className="flex flex-col gap-1">
              <label htmlFor="price-type" className="text-sm font-medium text-slate-800">
                Price type
              </label>
              <input
                id="price-type"
                name="price_type"
                type="text"
                placeholder="LAST, OFFICIAL_SETTLEMENT…"
                value={priceType}
                onChange={(event) => setPriceType(event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="quote-source" className="text-sm font-medium text-slate-800">
                Source
              </label>
              <input
                id="quote-source"
                name="source"
                type="text"
                placeholder="b3, tesouro…"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </>
        }
      />

      {state.status === "loading" ? <LoadingState label="Loading quote history…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}

      {state.status === "success" ? (
        <>
          <ProvenanceStrip items={quotes} />
          {quotes.length === 0 ? (
            <EmptyState>
              <p>No quotes in this window.</p>
              <p className="mt-2">
                The API returned an empty list — this explorer does not invent prices. Run{" "}
                <code className="font-mono text-xs">marketdata backfill</code> if you expected a
                series.
              </p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                label="Price"
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

export default function QuoteHistoryRoute() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Loading quote page…" />
        </div>
      }
    >
      <QuoteHistoryPage />
    </Suspense>
  );
}
