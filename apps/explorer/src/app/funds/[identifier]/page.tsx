"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DateRangeForm, type DateRangeValue } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LatestHeadline } from "@/components/LatestHeadline";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PriceChart } from "@/components/PriceChart";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { QuotesTable } from "@/components/QuotesTable";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchFundQuotes } from "@/lib/api";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import { useHistoryPages } from "@/lib/use-history-pages";

function FundQuotesPage() {
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const api = useApiStatus();
  const identifier = routeParam(params.identifier);
  const defaults = useMemo(() => defaultHistoryRange(5), []);
  const apiReady = api.status === "ok";

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
  });

  const key = JSON.stringify({ identifier, ...applied });
  const history = useHistoryPages({
    key,
    enabled: apiReady && Boolean(identifier),
    fetchPage: (cursor, signal) =>
      fetchFundQuotes(
        identifier,
        {
          start: applied.start || undefined,
          end: applied.end || undefined,
          cursor,
        },
        signal,
      ),
    itemsOf: (page) => page.quotes,
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
    router.replace(`/funds/${encodeURIComponent(identifier)}?${qs.toString()}`);
  }

  const quotes = history.items;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <p className="text-sm text-slate-500">Cotações de fundos</p>
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{identifier || "—"}</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/funds/{"{identifier}"}/quotes</code>
        </p>
        <LatestHeadline kind="fund" identifier={identifier} />
      </header>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
        disabled={!apiReady}
      />

      {api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando cotas…" />
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {history.status === "success" || quotes.length > 0 ? (
        <>
          <ProvenanceStrip items={quotes} />
          {quotes.length === 0 ? (
            <EmptyState>
              <p>Nenhuma cota neste intervalo.</p>
              <p className="mt-2 text-xs text-slate-500">
                Valor de cota ausente não é substituído por placeholder. Operadores: rode{" "}
                <code className="font-mono">marketdata backfill cvm</code> se esperava histórico
                deste CNPJ.
              </p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                label="Cota (NAV)"
                priceType={quotes[0]?.price_type ?? "FUND_NAV"}
                unit={quotes[0]?.unit}
                rows={quotes.map((quote) => ({ date: quote.date, raw: quote.price }))}
              />
              <QuotesTable quotes={quotes} />
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

export default function FundQuotesRoute() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Carregando página do fundo…" />
        </div>
      }
    >
      <FundQuotesPage />
    </Suspense>
  );
}
