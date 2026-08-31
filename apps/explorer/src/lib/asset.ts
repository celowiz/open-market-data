import {
  fetchFundLatest,
  fetchFundQuotes,
  fetchQuoteHistory,
  fetchQuoteLatest,
  fetchSeriesLatest,
  fetchSeriesObservations,
} from "@/lib/api";
import { addUtcMonths, todayIso } from "@/lib/dates";
import type { ExampleKind, HomeExample } from "@/lib/examples";
import { defaultPriceType } from "@/lib/identifiers";
import type { HistoryQuery, QuoteResponse, SeriesObservationResponse } from "@/lib/types";

export type LatestPrint = {
  date: string;
  value: string;
  extra: string;
  priceType?: string;
  unit?: string | null;
  kind: "quote" | "series";
};

export type HistoryPoint = {
  date: string;
  raw: string;
  priceType?: string;
  unit?: string | null;
  kind: "quote" | "series";
};

export function kindForIdentifier(identifier: string, assetClass = ""): ExampleKind {
  const trimmed = identifier.trim();
  if (assetClass === "fund" || /^\d{14}$/.test(trimmed)) {
    return "fund";
  }
  if (assetClass === "rate" || /^BCB:/i.test(trimmed)) {
    return "series";
  }
  return "quote";
}

export function hrefForKind(kind: ExampleKind, identifier: string): string {
  if (kind === "fund") {
    return `/funds/${encodeURIComponent(identifier)}`;
  }
  if (kind === "series") {
    return `/series/${encodeURIComponent(identifier)}`;
  }
  return `/quotes/${encodeURIComponent(identifier)}`;
}

export function exampleFromIdentifier(identifier: string, assetClass = ""): HomeExample {
  const kind = kindForIdentifier(identifier, assetClass);
  return {
    kind,
    title: identifier,
    identifier,
    href: hrefForKind(kind, identifier),
    description: "",
  };
}

export async function loadLatestPrint(
  example: Pick<HomeExample, "kind" | "identifier">,
  options?: { priceType?: string; signal?: AbortSignal },
): Promise<LatestPrint> {
  if (example.kind === "series") {
    const row = await fetchSeriesLatest(example.identifier, options?.signal);
    return seriesPrint(row);
  }
  if (example.kind === "fund") {
    const row = await fetchFundLatest(example.identifier, options?.signal);
    return quotePrint(row);
  }
  const row = await fetchQuoteLatest(example.identifier, {
    price_type: options?.priceType,
    signal: options?.signal,
  });
  return quotePrint(row);
}

export async function loadHistoryPage(
  kind: ExampleKind,
  identifier: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<{ points: HistoryPoint[]; nextCursor: string | null }> {
  if (kind === "series") {
    const page = await fetchSeriesObservations(identifier, params, signal);
    return {
      points: page.observations.map(seriesPoint),
      nextCursor: page.next_cursor,
    };
  }
  if (kind === "fund") {
    const page = await fetchFundQuotes(identifier, params, signal);
    return {
      points: page.quotes.map(quotePoint),
      nextCursor: page.next_cursor,
    };
  }
  const page = await fetchQuoteHistory(
    identifier,
    {
      ...params,
      price_type: params.price_type || defaultPriceType(identifier) || undefined,
    },
    signal,
  );
  return {
    points: page.quotes.map(quotePoint),
    nextCursor: page.next_cursor,
  };
}

export async function loadShortHistory(
  example: Pick<HomeExample, "kind" | "identifier">,
  signal?: AbortSignal,
): Promise<HistoryPoint[]> {
  const end = todayIso();
  const start = addUtcMonths(end, -1);
  const page = await loadHistoryPage(
    example.kind,
    example.identifier,
    { start, end, limit: 40 },
    signal,
  );
  return page.points;
}

function quotePrint(row: QuoteResponse): LatestPrint {
  return {
    date: row.date,
    value: row.price,
    extra: `${row.price_type} · ${row.source}`,
    priceType: row.price_type,
    unit: row.unit,
    kind: "quote",
  };
}

function seriesPrint(row: SeriesObservationResponse): LatestPrint {
  return {
    date: row.date,
    value: row.value,
    extra: `${row.unit} · ${row.source}`,
    unit: row.unit,
    kind: "series",
  };
}

function quotePoint(row: QuoteResponse): HistoryPoint {
  return {
    date: row.date,
    raw: row.price,
    priceType: row.price_type,
    unit: row.unit,
    kind: "quote",
  };
}

function seriesPoint(row: SeriesObservationResponse): HistoryPoint {
  return {
    date: row.date,
    raw: row.value,
    unit: row.unit,
    kind: "series",
  };
}
