import assert from "node:assert/strict";
import { test } from "node:test";

import {
  comboboxOptions,
  moveActiveIndex,
  optionDomId,
  SEARCH_SHORTCUT_IDENTIFIERS,
} from "./search-combobox.ts";

const shortcuts = SEARCH_SHORTCUT_IDENTIFIERS.map((identifier) => ({
  title: identifier,
  identifier,
  href: `/${identifier}`,
}));

test("empty query yields Brazilian shortcut chips, not Yahoo", () => {
  const options = comboboxOptions({ query: "   ", instruments: null, shortcuts });
  const ids = options.map((option) =>
    option.kind === "shortcut" ? option.example.identifier : option.id,
  );
  assert.deepEqual(ids, [
    "LTN:2029-01-01",
    "BCB:CDI_DAILY",
    "00017024000153",
    "PETR4",
    "DI1F27",
  ]);
  assert.equal(
    SEARCH_SHORTCUT_IDENTIFIERS.some((identifier) => identifier === "AAPL"),
    false,
  );
});

test("non-empty query never sends shortcut chips and ignores stale instruments", () => {
  assert.deepEqual(comboboxOptions({ query: "PETR", instruments: null, shortcuts }), []);
  const options = comboboxOptions({
    query: "PETR",
    instruments: [
      {
        instrument_id: "id-1",
        name: "PETR4",
        asset_class: "equity",
        identifiers: ["PETR4"],
        first_quote_date: "2024-01-02",
        last_quote_date: "2026-08-21",
        quote_count: 48,
      },
    ],
    shortcuts,
  });
  assert.equal(options.length, 1);
  assert.equal(options[0]?.kind, "instrument");
});

test("moveActiveIndex clamps without wrapping", () => {
  assert.equal(moveActiveIndex(0, 1, 0), -1);
  assert.equal(moveActiveIndex(-1, 1, 3), 0);
  assert.equal(moveActiveIndex(-1, -1, 3), 2);
  assert.equal(moveActiveIndex(0, -1, 3), 0);
  assert.equal(moveActiveIndex(2, 1, 3), 2);
  assert.equal(moveActiveIndex(1, 1, 3), 2);
});

test("optionDomId is stable for aria-activedescendant", () => {
  assert.equal(optionDomId("listbox-1", 0), "listbox-1-option-0");
});
