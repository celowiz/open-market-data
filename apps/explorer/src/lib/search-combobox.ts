import { BRAZIL_HOME_EXAMPLES, type HomeExample } from "./examples.ts";
import type { InstrumentSearchItem } from "./types.ts";

export const SEARCH_DEBOUNCE_MS = 300;

export type SearchComboboxOption =
  | { kind: "shortcut"; id: string; example: HomeExample }
  | { kind: "instrument"; id: string; item: InstrumentSearchItem };

export function searchShortcutExamples(): HomeExample[] {
  return BRAZIL_HOME_EXAMPLES;
}

export function comboboxOptions({
  query,
  instruments,
}: {
  query: string;
  instruments: InstrumentSearchItem[] | null;
}): SearchComboboxOption[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return searchShortcutExamples().map((example) => ({
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
