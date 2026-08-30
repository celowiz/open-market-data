import { copy } from "@/lib/copy";
import type {
  CoverageQuery,
  CoverageResponse,
  DatasetListing,
  FundQuotesResponse,
  HealthResponse,
  HistoryQuery,
  InstrumentsResponse,
  QuoteResponse,
  QuotesResponse,
  SeriesHistoryResponse,
  SeriesObservationResponse,
  SourceResponse,
} from "@/lib/types";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export const HISTORY_PAGE_SIZE = 500;
export const COVERAGE_PAGE_SIZE = 100;
export const INSTRUMENT_PAGE_SIZE = 20;

export type InstrumentsQuery = {
  q?: string;
  limit?: number;
  cursor?: string;
  source?: string;
  asset_class?: string;
};

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (raw) {
    return raw.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function isLoopbackApiHost(baseUrl = getApiBaseUrl()): boolean {
  try {
    const host = new URL(baseUrl).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
  } catch {
    return false;
  }
}

export function isLocalPageOrigin(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
}

export function shouldRevealApiBase(): boolean {
  return isLocalPageOrigin();
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) {
      continue;
    }
    const text = String(value).trim();
    if (text === "") {
      continue;
    }
    search.set(key, text);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function detailMessage(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("detail" in body)) {
    return null;
  }
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        try {
          return JSON.stringify(item);
        } catch {
          return String(item);
        }
      })
      .join("; ");
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export function isNetworkFailure(error: unknown): boolean {
  if (error instanceof TypeError) {
    return true;
  }
  if (!(error instanceof Error)) {
    return false;
  }
  return /failed to fetch|networkerror|load failed|fetch failed/i.test(error.message);
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = detailMessage(error.body);
    if (detail) {
      return `${error.status}: ${detail}`;
    }
    if (typeof error.body === "string" && error.body.trim()) {
      return `${error.status}: ${error.body}`;
    }
    return error.message;
  }
  if (isNetworkFailure(error)) {
    if (isLocalPageOrigin()) {
      return copy.api.localUnreachable(getApiBaseUrl());
    }
    return copy.api.publicUnavailable;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return copy.api.unknown;
}

export function isNotFoundError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 404;
  }
  const message = formatApiError(error).toLowerCase();
  return message.includes("404") || message.includes("not found");
}

export async function apiFetch<T>(
  path: string,
  options?: {
    query?: Record<string, string | number | undefined | null>;
    signal?: AbortSignal;
  },
): Promise<T> {
  const url = `${getApiBaseUrl()}${path}${buildQuery(options?.query ?? {})}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: options?.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw error;
  }

  const contentType = response.headers.get("content-type") ?? "";
  let body: unknown = null;
  if (contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  } else {
    const text = await response.text();
    body = text || null;
  }

  if (!response.ok) {
    const detail = detailMessage(body);
    throw new ApiError(
      response.status,
      body,
      detail ? `${response.status}: ${detail}` : `HTTP ${response.status} for ${path}`,
    );
  }

  return body as T;
}

function historyQuery(params: HistoryQuery): Record<string, string | number | undefined | null> {
  return {
    start: params.start,
    end: params.end,
    limit: params.limit ?? HISTORY_PAGE_SIZE,
    cursor: params.cursor,
    price_type: params.price_type,
    source: params.source,
  };
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/v1/health", { signal });
}

export function listInstruments(
  query: InstrumentsQuery = {},
  signal?: AbortSignal,
): Promise<InstrumentsResponse> {
  return apiFetch<InstrumentsResponse>("/v1/instruments", {
    query: {
      q: query.q,
      limit: query.limit ?? INSTRUMENT_PAGE_SIZE,
      cursor: query.cursor,
      source: query.source,
      asset_class: query.asset_class,
    },
    signal,
  });
}

export function searchInstruments(
  q: string,
  limit = INSTRUMENT_PAGE_SIZE,
  signal?: AbortSignal,
): Promise<InstrumentsResponse> {
  return listInstruments({ q, limit }, signal);
}

export async function lookupInstrumentName(
  q: string,
  signal?: AbortSignal,
): Promise<string | null> {
  const data = await searchInstruments(q, 5, signal);
  const needle = q.trim().toLowerCase();
  const match =
    data.instruments.find((item) =>
      item.identifiers.some((id) => id.toLowerCase() === needle),
    ) ?? data.instruments.find((item) => item.name.toLowerCase() === needle);
  return match?.name ?? null;
}

export function fetchQuoteHistory(
  identifier: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<QuotesResponse> {
  return apiFetch<QuotesResponse>(`/v1/quotes/${encodePathSegment(identifier)}/history`, {
    query: historyQuery(params),
    signal,
  });
}

export function fetchQuoteLatest(
  identifier: string,
  params?: { price_type?: string; source?: string; signal?: AbortSignal },
): Promise<QuoteResponse> {
  return apiFetch<QuoteResponse>(`/v1/quotes/${encodePathSegment(identifier)}/latest`, {
    query: { price_type: params?.price_type, source: params?.source },
    signal: params?.signal,
  });
}

export function fetchSeriesObservations(
  code: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<SeriesHistoryResponse> {
  return apiFetch<SeriesHistoryResponse>(`/v1/series/${encodePathSegment(code)}/observations`, {
    query: historyQuery(params),
    signal,
  });
}

export function fetchSeriesLatest(
  code: string,
  signal?: AbortSignal,
): Promise<SeriesObservationResponse> {
  return apiFetch<SeriesObservationResponse>(`/v1/series/${encodePathSegment(code)}/latest`, {
    signal,
  });
}

export function fetchFundQuotes(
  identifier: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<FundQuotesResponse> {
  return apiFetch<FundQuotesResponse>(`/v1/funds/${encodePathSegment(identifier)}/quotes`, {
    query: historyQuery(params),
    signal,
  });
}

export function fetchFundLatest(
  identifier: string,
  signal?: AbortSignal,
): Promise<QuoteResponse> {
  return apiFetch<QuoteResponse>(`/v1/funds/${encodePathSegment(identifier)}/quotes/latest`, {
    signal,
  });
}

export function fetchSources(signal?: AbortSignal): Promise<SourceResponse[]> {
  return apiFetch<SourceResponse[]>("/v1/sources", { signal });
}

export function fetchDatasets(signal?: AbortSignal): Promise<DatasetListing[]> {
  return apiFetch<DatasetListing[]>("/v1/datasets", { signal });
}

export function fetchDataset(name: string, signal?: AbortSignal): Promise<DatasetListing> {
  return apiFetch<DatasetListing>(`/v1/datasets/${encodePathSegment(name)}`, { signal });
}

export function fetchCoverage(params: CoverageQuery, signal?: AbortSignal): Promise<CoverageResponse> {
  return apiFetch<CoverageResponse>("/v1/coverage", {
    query: {
      date: params.date,
      universe: params.universe,
      limit: params.limit ?? COVERAGE_PAGE_SIZE,
      cursor: params.cursor,
    },
    signal,
  });
}
