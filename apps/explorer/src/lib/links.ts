import type { InstrumentSearchItem } from "@/lib/types";

export function hrefForInstrument(item: InstrumentSearchItem): string {
  if (item.asset_class === "fund") {
    const cnpj = item.identifiers.find((id) => /^\d{14}$/.test(id));
    const id = cnpj ?? item.identifiers[0];
    if (id) {
      return `/funds/${encodeURIComponent(id)}`;
    }
  }
  const seriesId = item.identifiers.find((id) => id.toUpperCase().startsWith("BCB:"));
  if (seriesId || item.asset_class === "rate") {
    const id = seriesId ?? item.identifiers[0];
    if (id) {
      return `/series/${encodeURIComponent(id)}`;
    }
  }
  const id = item.identifiers[0];
  if (id) {
    return `/quotes/${encodeURIComponent(id)}`;
  }
  return `/quotes/${encodeURIComponent(item.instrument_id)}`;
}

export function guessOpenTarget(q: string): { href: string; label: string } | null {
  const trimmed = q.trim();
  if (!trimmed) {
    return null;
  }
  if (/^BCB:/i.test(trimmed)) {
    return {
      href: `/series/${encodeURIComponent(trimmed)}`,
      label: `Open series ${trimmed}`,
    };
  }
  if (/^\d{14}$/.test(trimmed)) {
    return {
      href: `/funds/${encodeURIComponent(trimmed)}`,
      label: `Open fund ${trimmed}`,
    };
  }
  return {
    href: `/quotes/${encodeURIComponent(trimmed)}`,
    label: `Open quotes ${trimmed}`,
  };
}

export const BLOCKED_DATASET_SOURCES = new Set(["b3", "yahoo"]);

export function isBlockedDatasetDownload(sources: string[], datasetName: string): boolean {
  const name = datasetName.toLowerCase();
  if (name.includes("b3") || name.includes("yahoo")) {
    return true;
  }
  return sources.some((source) => BLOCKED_DATASET_SOURCES.has(source.toLowerCase()));
}
