"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AssetRow, AssetRowList } from "@/components/AssetRow";
import { useApiStatus } from "@/components/ApiStatusProvider";
import { CoverageSpanChip } from "@/components/CoverageSpanChip";
import { DeltaBadge } from "@/components/DeltaBadge";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ChartSkeleton, EmptyState, RowSkeleton } from "@/components/Status";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PriceChart } from "@/components/PriceChart";
import { RangeChips, rangeFromKey, type RangeKey } from "@/components/RangeChips";
import { useSearchQuery } from "@/components/SearchQueryProvider";
import {
  exampleFromIdentifier,
  hrefForKind,
  loadHistoryPage,
  loadLatestPrint,
  loadShortHistory,
} from "@/lib/asset";
import { formatApiError, isNotFoundError, lookupInstrumentName, searchInstruments } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatDisplayValue } from "@/lib/format-display-value";
import { BRAZIL_HOME_EXAMPLES, DEFAULT_HERO_EXAMPLES, type ExampleKind, type HomeExample } from "@/lib/examples";
import { formatQuoteSpan, pickInstrumentMatch } from "@/lib/span";
import { hrefForInstrument } from "@/lib/links";
import type { InstrumentSearchItem } from "@/lib/types";
import { useClientFetch } from "@/lib/use-client-fetch";
import { useHistoryPages } from "@/lib/use-history-pages";
import { windowDeltaFromRows } from "@/lib/window-delta";

export function HomeTradingView() {
  const api = useApiStatus();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { query } = useSearchQuery();
  const apiReady = api.status === "ok";
  const selectedId = searchParams.get("id")?.trim() ?? "";
  const selectedKind = (searchParams.get("kind") as ExampleKind | null) ?? undefined;
  const [rangeKey, setRangeKey] = useState<RangeKey>("1A");
  const range = useMemo(() => rangeFromKey(rangeKey), [rangeKey]);
  const [probed, setProbed] = useState(false);

  useEffect(() => {
    if (!apiReady || selectedId || probed) {
      return;
    }
    let cancelled = false;
    (async () => {
      for (const example of DEFAULT_HERO_EXAMPLES) {
        try {
          await loadLatestPrint(example);
          if (!cancelled) {
            const params = new URLSearchParams();
            params.set("id", example.identifier);
            params.set("kind", example.kind);
            router.replace(`/?${params.toString()}`, { scroll: false });
            setProbed(true);
          }
          return;
        } catch {
          // try the next identifier; never invent a print
        }
      }
      if (!cancelled) {
        setProbed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiReady, probed, router, selectedId]);

  const selected = selectedId
    ? exampleFromIdentifier(selectedId, selectedKind === "fund" ? "fund" : selectedKind === "series" ? "rate" : "")
    : null;
  if (selected && selectedKind) {
    selected.kind = selectedKind;
    selected.href = hrefForKind(selectedKind, selected.identifier);
  }

  function selectExample(example: HomeExample) {
    const params = new URLSearchParams();
    params.set("id", example.identifier);
    params.set("kind", example.kind);
    router.replace(`/?${params.toString()}`, { scroll: false });
  }

  return (
    <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:gap-10">
      <section className="min-w-0 flex-1" aria-labelledby="hero-heading">
        {selected ? (
          <HomeHero
            example={selected}
            rangeKey={rangeKey}
            range={range}
            onRange={(key) => setRangeKey(key)}
          />
        ) : apiReady && !probed ? (
          <ChartSkeleton label="Escolhendo ativo…" />
        ) : (
          <EmptyState>
            <h1 id="hero-heading" className="text-lg font-semibold text-foreground">
              Nenhum preço disponível ainda
            </h1>
            <p className="mt-2">{copy.common.noSynthetic}.</p>
            <p className="mt-2 text-xs">{copy.common.historyLoading}</p>
          </EmptyState>
        )}
      </section>
      <aside className="w-full shrink-0 lg:w-[22rem]" aria-labelledby="watchlist-heading">
        <div className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-2">
            <h2 id="watchlist-heading" className="text-sm font-semibold text-foreground">
              {copy.common.watchlist}
            </h2>
            <Link href="/ativos" className="text-xs font-medium text-accent hover:underline">
              {copy.nav.instruments}
            </Link>
          </div>
          <CoverageSpanChip />
          <Watchlist
            selectedId={selectedId}
            onSelect={selectExample}
            searchQuery={query}
            apiReady={apiReady}
          />
        </div>
      </aside>
    </div>
  );
}

function HomeHero({
  example,
  rangeKey,
  range,
  onRange,
}: {
  example: HomeExample;
  rangeKey: RangeKey;
  range: { start: string; end: string };
  onRange: (key: RangeKey) => void;
}) {
  const api = useApiStatus();
  const apiReady = api.status === "ok";
  const history = useHistoryPages({
    key: JSON.stringify({
      id: example.identifier,
      kind: example.kind,
      start: range.start,
      end: range.end,
    }),
    enabled: apiReady && Boolean(example.identifier),
    fetchPage: (cursor, signal) =>
      loadHistoryPage(
        example.kind,
        example.identifier,
        { start: range.start || undefined, end: range.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.points,
    cursorOf: (page) => page.nextCursor,
  });
  const name = useClientFetch(
    `name:${example.identifier}`,
    () => lookupInstrumentName(example.identifier),
    { enabled: apiReady },
  );
  const catalog = useClientFetch(
    `hero-span:${example.identifier}`,
    () => searchInstruments(example.identifier, 5),
    { enabled: apiReady },
  );
  const points = history.items;
  const last = points.length > 0 ? points[points.length - 1] : null;
  const sorted = [...points].sort((a, b) => a.date.localeCompare(b.date));
  const lastPoint = sorted[sorted.length - 1] ?? last;
  const delta = windowDeltaFromRows(sorted);
  const match =
    catalog.status === "success"
      ? pickInstrumentMatch(catalog.data.instruments, example.identifier)
      : null;
  const displayName =
    name.status === "success" && name.data && name.data !== example.identifier ? name.data : example.title;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">{example.title}</p>
        <h1 id="hero-heading" className="font-mono text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {example.identifier}
        </h1>
        {displayName && displayName !== example.identifier ? (
          <p className="text-sm text-muted">{displayName}</p>
        ) : null}
      </div>
      {api.status !== "unreachable" && history.status === "loading" ? (
        <div className="flex flex-col gap-3">
          <div className="skeleton h-10 w-40 rounded" />
          <ChartSkeleton />
        </div>
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}
      {lastPoint ? (
        <div className="flex flex-wrap items-end gap-3">
          <p className="font-mono text-4xl font-semibold tabular-nums tracking-tight text-foreground sm:text-5xl">
            {formatDisplayValue(lastPoint.raw, {
              priceType: lastPoint.priceType,
              unit: lastPoint.unit,
              kind: lastPoint.kind,
            })}
          </p>
          {delta ? <DeltaBadge delta={delta} /> : null}
          <p className="text-sm text-muted">{lastPoint.date}</p>
        </div>
      ) : null}
      {match ? (
        <p className="font-mono text-xs text-muted">{formatQuoteSpan(match)}</p>
      ) : null}
      <RangeChips value={rangeKey} disabled={!apiReady} onChange={(key) => onRange(key)} />
      {points.length > 0 ? (
        <PriceChart
          variant="hero"
          label={example.identifier}
          priceType={lastPoint?.priceType}
          unit={lastPoint?.unit}
          kind={lastPoint?.kind}
          rows={points.map((point) => ({ date: point.date, raw: point.raw }))}
        />
      ) : null}
      {history.status === "success" && points.length === 0 ? (
        <EmptyState>
          <p>Nenhuma cotação neste intervalo.</p>
          <p className="mt-2 text-xs">{copy.common.noSynthetic}.</p>
        </EmptyState>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Link href={example.href} className="text-sm font-medium text-accent hover:underline">
          {copy.common.openHistory}
        </Link>
        <LoadMoreButton
          hasMore={history.hasMore}
          loading={history.loadingMore}
          onClick={history.loadMore}
        />
      </div>
    </div>
  );
}

function Watchlist({
  selectedId,
  onSelect,
  searchQuery,
  apiReady,
}: {
  selectedId: string;
  onSelect: (example: HomeExample) => void;
  searchQuery: string;
  apiReady: boolean;
}) {
  const trimmed = searchQuery.trim();
  const search = useClientFetch(
    `watch-search:${trimmed}`,
    () => searchInstruments(trimmed, 20),
    { enabled: apiReady && Boolean(trimmed) },
  );

  const searchItems: InstrumentSearchItem[] =
    trimmed && search.status === "success" ? search.data.instruments : [];
  const searchIds = new Set(
    searchItems.flatMap((item) => item.identifiers.map((id) => id.toLowerCase())),
  );

  return (
    <div className="flex flex-col gap-4">
      {trimmed ? (
        <div className="flex flex-col gap-1">
          {search.status === "loading" ? <RowSkeleton count={4} /> : null}
          {search.status === "error" ? <ErrorBanner error={search.error} /> : null}
          {search.status === "success" && searchItems.length === 0 ? (
            <p className="px-3 text-sm text-muted">Nenhum instrumento nesta consulta.</p>
          ) : null}
          {searchItems.length > 0 ? (
            <AssetRowList label="Resultados da busca">
              {searchItems.map((item) => (
                <li key={item.instrument_id}>
                  <SearchWatchRow
                    item={item}
                    selected={item.identifiers.some((id) => id.toLowerCase() === selectedId.toLowerCase())}
                    onSelect={onSelect}
                  />
                </li>
              ))}
            </AssetRowList>
          ) : null}
        </div>
      ) : null}
      <AssetRowList label={copy.common.examples}>
        {BRAZIL_HOME_EXAMPLES.filter(
          (example) => !searchIds.has(example.identifier.toLowerCase()),
        ).map((example) => (
          <li key={example.identifier}>
            <ExampleWatchRow
              example={example}
              selected={example.identifier.toLowerCase() === selectedId.toLowerCase()}
              onSelect={() => onSelect(example)}
            />
          </li>
        ))}
      </AssetRowList>
    </div>
  );
}

function ExampleWatchRow({
  example,
  selected,
  onSelect,
}: {
  example: HomeExample;
  selected: boolean;
  onSelect: () => void;
}) {
  const api = useApiStatus();
  const enabled = api.status === "ok";
  const latest = useClientFetch(`watch-latest:${example.kind}:${example.identifier}`, () =>
    loadLatestPrint(example), { enabled });
  const history = useClientFetch(`watch-hist:${example.kind}:${example.identifier}`, () =>
    loadShortHistory(example), { enabled });
  const catalog = useClientFetch(`watch-span:${example.identifier}`, () =>
    searchInstruments(example.identifier, 5), { enabled });
  const match =
    catalog.status === "success"
      ? pickInstrumentMatch(catalog.data.instruments, example.identifier)
      : null;
  const errorText =
    latest.status === "error"
      ? `${formatApiError(latest.error)}${isNotFoundError(latest.error) ? ` — ${copy.common.noSynthetic}` : ""}`
      : undefined;

  return (
    <AssetRow
      identifier={example.identifier}
      title={example.title}
      href={example.href}
      selected={selected}
      onSelect={onSelect}
      latest={latest.status === "success" ? latest.data : undefined}
      history={history.status === "success" ? history.data : undefined}
      loading={enabled && latest.status === "loading"}
      errorText={errorText}
      span={match ?? undefined}
    />
  );
}

function SearchWatchRow({
  item,
  selected,
  onSelect,
}: {
  item: InstrumentSearchItem;
  selected: boolean;
  onSelect: (example: HomeExample) => void;
}) {
  const identifier = item.identifiers[0] ?? item.instrument_id;
  const example = exampleFromIdentifier(identifier, item.asset_class);
  const api = useApiStatus();
  const latest = useClientFetch(
    `search-latest:${example.kind}:${example.identifier}`,
    () => loadLatestPrint(example),
    { enabled: api.status === "ok" },
  );
  return (
    <AssetRow
      identifier={identifier}
      title={item.name}
      href={hrefForInstrument(item)}
      selected={selected}
      onSelect={() => onSelect(example)}
      latest={latest.status === "success" ? latest.data : undefined}
      loading={api.status === "ok" && latest.status === "loading"}
      span={item}
    />
  );
}
