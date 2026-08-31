import type { InstrumentSearchItem } from "./types";

export const SEARCH_DEBOUNCE_MS = 300;

export type SearchShortcut = {
  title: string;
  identifier: string;
  href: string;
};

export type SearchComboboxOption =
  | { kind: "shortcut"; id: string; example: SearchShortcut }
  | { kind: "instrument"; id: string; item: InstrumentSearchItem };

export const SEARCH_SHORTCUT_IDENTIFIERS = [
  "LTN:2029-01-01",
  "BCB:CDI_DAILY",
  "00017024000153",
  "PETR4",
  "DI1F27",
] as const;

export function comboboxOptions({
  query,
  instruments,
  shortcuts,
}: {
  query: string;
  instruments: InstrumentSearchItem[] | null;
  shortcuts: SearchShortcut[];
}): SearchComboboxOption[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return shortcuts.map((example) => ({
      kind: "shortcut",
      id: `shortcut:${example.identifier}`,
      example,
    }));
  }
  if (!instruments) {
    return [];
  }
  return instruments.map((item) => ({
    kind: "instrument",
    id: item.instrument_id,
    item,
  }));
}

export function moveActiveIndex(current: number, delta: number, length: number): number {
  if (length <= 0) {
    return -1;
  }
  if (current < 0) {
    return delta > 0 ? 0 : length - 1;
  }
  const next = current + delta;
  if (next < 0) {
    return 0;
  }
  if (next >= length) {
    return length - 1;
  }
  return next;
}

export function optionDomId(listboxId: string, index: number): string {
  return `${listboxId}-option-${index}`;
}
