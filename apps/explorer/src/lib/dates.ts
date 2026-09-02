import type { QuoteSpanFields } from "./span";

export function formatLocalIso(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function defaultHistoryRange(years = 5): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setFullYear(start.getFullYear() - years);
  return { start: formatLocalIso(start), end: formatLocalIso(end) };
}

export function todayIso(): string {
  return formatLocalIso(new Date());
}

export function addUtcMonths(iso: string, months: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCMonth(date.getUTCMonth() + months);
  return date.toISOString().slice(0, 10);
}

export function addUtcYears(iso: string, years: number): string {
  return addUtcMonths(iso, years * 12);
}

export function addUtcDays(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

export function utcDayDiff(start: string, end: string): number {
  const from = Date.parse(`${start}T00:00:00Z`);
  const to = Date.parse(`${end}T00:00:00Z`);
  return Math.round((to - from) / 86_400_000);
}

export function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function routeParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return safeDecode(value[0] ?? "");
  }
  return safeDecode(value ?? "");
}

export type DateRangeValue = {
  start: string;
  end: string;
};

export type RangeKey = "1M" | "1A" | "5A" | "max";

export const DEFAULT_HISTORY_RANGE_KEY: RangeKey = "max";

export function rangeFromQuoteSpan(span?: QuoteSpanFields | null): DateRangeValue | null {
  const start = span?.first_quote_date?.trim() || "";
  const end = span?.last_quote_date?.trim() || "";
  if (!start && !end) {
    return null;
  }
  return { start, end: end || todayIso() };
}

export function rangeFromKey(key: RangeKey, span?: QuoteSpanFields | null): DateRangeValue {
  const today = todayIso();
  if (key === "1M") {
    return { start: addUtcMonths(today, -1), end: today };
  }
  if (key === "1A") {
    return { start: addUtcYears(today, -1), end: today };
  }
  if (key === "5A") {
    return { start: defaultHistoryRange(5).start, end: today };
  }
  return rangeFromQuoteSpan(span) ?? { start: "", end: today };
}

export function defaultChartRange(span?: QuoteSpanFields | null): DateRangeValue {
  return rangeFromKey(DEFAULT_HISTORY_RANGE_KEY, span);
}

