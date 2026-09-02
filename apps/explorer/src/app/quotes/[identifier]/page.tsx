"use client";

import { Suspense, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DateRangeForm, type DateRangeValue } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LatestHeadline } from "@/components/LatestHeadline";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PageShell } from "@/components/PageShell";
import { PriceChart } from "@/components/PriceChart";
import { PriceTypeFilters } from "@/components/PriceTypeFilters";
import { ProvenanceStrip } from "@/components/ProvenanceStrip";
import { QuotesTable } from "@/components/QuotesTable";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchQuoteHistory } from "@/lib/api";
import { copy } from "@/lib/copy";
import { defaultHistoryRange, routeParam } from "@/lib/dates";
import {
  FUTURE_PRICE_TYPES,
  TESOURO_PRICE_TYPES,
  defaultPriceType,
  isB3FutureIdentifier,
  isTesouroIdentifier,
  tesouroCompanionPriceType,
} from "@/lib/identifiers";
import { formatQuoteSpan, hasQuoteSpan } from "@/lib/span";
import { fieldClass } from "@/lib/ui";
import { useHistoryPages } from "@/lib/use-history-pages";
import { windowDeltaFromRows } from "@/lib/window-delta";
import { DeltaBadge } from "@/components/DeltaBadge";
import { EventsList } from "@/components/EventsList";
import { LendingPanel } from "@/components/LendingPanel";

function QuoteHistoryPage() {
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const api = useApiStatus();
  const identifier = routeParam(params.identifier);
  const defaults = useMemo(() => defaultHistoryRange(5), []);
  const tesouro = isTesouroIdentifier(identifier);
  const future = isB3FutureIdentifier(identifier);
  const initialPriceType = searchParams.get("price_type") ?? defaultPriceType(identifier);

  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [priceType, setPriceType] = useState(initialPriceType);
  const [source, setSource] = useState(searchParams.get("source") ?? "");
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
    price_type: initialPriceType,
    source: searchParams.get("source") ?? "",
  });

  const apiReady = api.status === "ok";
  const key = JSON.stringify({ identifier, ...applied });
  const companionType = tesouro ? tesouroCompanionPriceType(applied.price_type || "PU_BASE") : null;
  const companionKey = JSON.stringify({ identifier, ...applied, price_type: companionType });

  const history = useHistoryPages({
    key,
    enabled: apiReady && Boolean(identifier),
    fetchPage: (cursor, signal) =>
      fetchQuoteHistory(
        identifier,
        {
          start: applied.start || undefined,
          end: applied.end || undefined,
          price_type: applied.price_type || undefined,
          source: applied.source || undefined,
          cursor,
        },
        signal,
      ),
    itemsOf: (page) => page.quotes,
    cursorOf: (page) => page.next_cursor,
  });

  const companion = useHistoryPages({
    key: companionKey,
    enabled: apiReady && Boolean(identifier) && Boolean(companionType),
    fetchPage: (cursor, signal) =>
      fetchQuoteHistory(
        identifier,
        {
          start: applied.start || undefined,
          end: applied.end || undefined,
          price_type: companionType ?? undefined,
          source: applied.source || undefined,
          cursor,
        },
        signal,
      ),
    itemsOf: (page) => page.quotes,
    cursorOf: (page) => page.next_cursor,
  });

  function applyFilters(range?: DateRangeValue, nextPriceType = priceType) {
    const next = {
      start: range?.start ?? start,
      end: range?.end ?? end,
      price_type: nextPriceType,
      source,
    };
    setStart(next.start);
    setEnd(next.end);
    setApplied(next);
    const qs = new URLSearchParams();
    if (next.start) qs.set("start", next.start);
    if (next.end) qs.set("end", next.end);
    if (next.price_type.trim()) qs.set("price_type", next.price_type.trim());
    if (next.source.trim()) qs.set("source", next.source.trim());
    router.replace(`/quotes/${encodeURIComponent(identifier)}?${qs.toString()}`);
  }

  const quotes = history.items;
  const primaryUnit = quotes[0]?.unit ?? quotes[0]?.price_type ?? "PU";
  const companionUnit = companion.items[0]?.unit ?? companionType ?? "YIELD";
  const windowDelta = windowDeltaFromRows(quotes.map((quote) => ({ date: quote.date, raw: quote.price })));
  const spanLabel = history.firstPage ? formatQuoteSpan(history.firstPage) : null;

  return (
    <PageShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Cotação</p>
        <h1 className="font-mono text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {identifier || "—"}
        </h1>
        <LatestHeadline kind="quote" identifier={identifier} priceType={applied.price_type} />
        <LendingPanel identifier={identifier} />
        <EventsList identifier={identifier} />
        {windowDelta ? (
          <p className="text-sm text-muted">
            {copy.common.windowChange}: <DeltaBadge delta={windowDelta} />
          </p>
        ) : null}
        {spanLabel ? <p className="font-mono text-xs text-muted">{spanLabel}</p> : null}
        {history.status === "success" && (!history.firstPage || !hasQuoteSpan(history.firstPage)) ? (
          <p className="text-sm text-muted">{copy.common.historyLoading}</p>
        ) : null}
      </header>

      {tesouro ? (
        <PriceTypeFilters
          label="Tipos Tesouro"
          options={TESOURO_PRICE_TYPES}
          value={priceType}
          onChange={(value) => {
            setPriceType(value);
            applyFilters(undefined, value);
          }}
        />
      ) : null}
      {future ? (
        <PriceTypeFilters
          label="Tipos de futuro"
          options={FUTURE_PRICE_TYPES}
          value={priceType || "OFFICIAL_SETTLEMENT"}
          onChange={(value) => {
            setPriceType(value);
            applyFilters(undefined, value);
          }}
        />
      ) : null}

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
        disabled={!apiReady}
        extra={
          <>
            {tesouro || future ? null : (
              <div className="flex flex-col gap-1">
                <label htmlFor="price-type" className="text-sm font-medium text-foreground">
                  {copy.common.priceType}
                </label>
                <input
                  id="price-type"
                  name="price_type"
                  type="text"
                  placeholder="LAST, OFFICIAL_SETTLEMENT…"
                  value={priceType}
                  disabled={!apiReady}
                  onChange={(event) => setPriceType(event.target.value)}
                  className={fieldClass}
                />
              </div>
            )}
            <div className="flex flex-col gap-1">
              <label htmlFor="quote-source" className="text-sm font-medium text-foreground">
                {copy.common.source}
              </label>
              <input
                id="quote-source"
                name="source"
                type="text"
                placeholder="b3, tesouro…"
                value={source}
                disabled={!apiReady}
                onChange={(event) => setSource(event.target.value)}
                className={fieldClass}
              />
            </div>
          </>
        }
      />

      {api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando histórico de cotações…" />
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}
      {companionType && companion.status === "error" ? (
        <ErrorBanner error={companion.error} />
      ) : null}

      {history.status === "success" || quotes.length > 0 ? (
        <>
          {quotes.length === 0 ? (
            <EmptyState>
              <p>Nenhuma cotação neste intervalo.</p>
              <p className="mt-2 text-xs">{copy.common.historyLoading}</p>
            </EmptyState>
          ) : (
            <>
              <PriceChart
                variant="hero"
                label={`${applied.price_type || "Preço"} (${primaryUnit})`}
                priceType={applied.price_type || quotes[0]?.price_type}
                unit={quotes[0]?.unit}
                rows={quotes.map((quote) => ({ date: quote.date, raw: quote.price }))}
              />
              {tesouro && companionType && companion.items.length > 0 ? (
                <section className="flex flex-col gap-2">
                  <h2 className="text-sm font-semibold text-foreground">
                    Série complementar {companionType} ({companionUnit}) — eixo separado
                  </h2>
                  <PriceChart
                    label={`${companionType} (${companionUnit})`}
                    priceType={companionType}
                    unit={companion.items[0]?.unit}
                    rows={companion.items.map((quote) => ({ date: quote.date, raw: quote.price }))}
                  />
                </section>
              ) : null}
              <ProvenanceStrip items={quotes} />
              <QuotesTable quotes={quotes} />
              <LoadMoreButton
                hasMore={history.hasMore}
                loading={history.loadingMore}
                onClick={() => {
                  history.loadMore();
                  if (companionType) {
                    companion.loadMore();
                  }
                }}
              />
            </>
          )}
        </>
      ) : null}
    </PageShell>
  );
}

export default function QuoteHistoryRoute() {
  return (
    <Suspense
      fallback={
        <PageShell>
          <LoadingState label="Carregando página de cotações…" />
        </PageShell>
      }
    >
      <QuoteHistoryPage />
    </Suspense>
  );
}
