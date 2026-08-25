import type {
  CoverageResponse,
  DatasetListing,
  FundQuotesResponse,
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

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (raw) {
    return raw.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
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
  if (error instanceof TypeError) {
    return `Cannot reach ${getApiBaseUrl()}. Start FastAPI (uvicorn on port 8000) and set CORS_ALLOWED_ORIGINS to include this Explorer origin (http://localhost:3000).`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
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

const HISTORY_LIMIT = 5000;

function historyQuery(params: HistoryQuery): Record<string, string | number | undefined | null> {
  return {
    start: params.start,
    end: params.end,
    limit: params.limit ?? HISTORY_LIMIT,
    cursor: params.cursor,
    price_type: params.price_type,
    source: params.source,
  };
}

export function searchInstruments(
  q: string,
  limit = 20,
  signal?: AbortSignal,
): Promise<InstrumentsResponse> {
  return apiFetch<InstrumentsResponse>("/v1/instruments", {
    query: { q, limit },
    signal,
  });
}

export function fetchQuoteHistory(
  identifier: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<QuotesResponse> {
  return apiFetch<QuotesResponse>(
    `/v1/quotes/${encodePathSegment(identifier)}/history`,
    { query: historyQuery(params), signal },
  );
}

export function fetchQuoteLatest(
  identifier: string,
  signal?: AbortSignal,
): Promise<QuoteResponse> {
  return apiFetch<QuoteResponse>(`/v1/quotes/${encodePathSegment(identifier)}/latest`, {
    signal,
  });
}

export function fetchSeriesObservations(
  code: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<SeriesHistoryResponse> {
  return apiFetch<SeriesHistoryResponse>(
    `/v1/series/${encodePathSegment(code)}/observations`,
    { query: historyQuery(params), signal },
  );
}

export function fetchSeriesLatest(
  code: string,
  signal?: AbortSignal,
): Promise<SeriesObservationResponse> {
  return apiFetch<SeriesObservationResponse>(
    `/v1/series/${encodePathSegment(code)}/latest`,
    { signal },
  );
}

export function fetchFundQuotes(
  identifier: string,
  params: HistoryQuery,
  signal?: AbortSignal,
): Promise<FundQuotesResponse> {
  return apiFetch<FundQuotesResponse>(
    `/v1/funds/${encodePathSegment(identifier)}/quotes`,
    { query: historyQuery(params), signal },
  );
}

export function fetchFundLatest(
  identifier: string,
  signal?: AbortSignal,
): Promise<QuoteResponse> {
  return apiFetch<QuoteResponse>(
    `/v1/funds/${encodePathSegment(identifier)}/quotes/latest`,
    { signal },
  );
}

export function fetchSources(signal?: AbortSignal): Promise<SourceResponse[]> {
  return apiFetch<SourceResponse[]>("/v1/sources", { signal });
}

export function fetchDatasets(signal?: AbortSignal): Promise<DatasetListing[]> {
  return apiFetch<DatasetListing[]>("/v1/datasets", { signal });
}

export function fetchCoverage(
  date: string,
  signal?: AbortSignal,
): Promise<CoverageResponse> {
  return apiFetch<CoverageResponse>("/v1/coverage", {
    query: { date },
    signal,
  });
}
