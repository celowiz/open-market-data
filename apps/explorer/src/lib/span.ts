import type { InstrumentSearchItem } from "@/lib/types";

export type QuoteSpanFields = {
  first_quote_date?: string | null;
  last_quote_date?: string | null;
  quote_count?: number | null;
};

export function formatPregoes(count: number | null | undefined): string {
  if (count == null) {
    return "—";
  }
  const formatted = count.toLocaleString("pt-BR");
  return count === 1 ? `${formatted} pregão` : `${formatted} pregões`;
}

export function hasQuoteSpan(span: QuoteSpanFields): boolean {
  return Boolean(
    span.first_quote_date || span.last_quote_date || (span.quote_count != null && span.quote_count > 0),
  );
}

export function formatQuoteSpan(span: QuoteSpanFields): string | null {
  if (!hasQuoteSpan(span)) {
    return null;
  }
  const start = span.first_quote_date ?? null;
  const end = span.last_quote_date ?? null;
  const range = start && end ? `${start} → ${end}` : (start ?? end);
  const count = span.quote_count != null ? formatPregoes(span.quote_count) : null;
  const text = [range, count].filter(Boolean).join(" · ");
  return text || null;
}

export function pickInstrumentMatch(
  items: InstrumentSearchItem[],
  identifier: string,
): InstrumentSearchItem | null {
  const needle = identifier.trim().toLowerCase();
  if (!needle) {
    return null;
  }
  return (
    items.find((item) => item.identifiers.some((id) => id.toLowerCase() === needle)) ??
    items.find((item) => item.instrument_id.toLowerCase() === needle) ??
    items.find((item) => item.name.toLowerCase() === needle) ??
    null
  );
}
