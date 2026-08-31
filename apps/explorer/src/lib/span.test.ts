import assert from "node:assert/strict";
import { test } from "node:test";

import { formatPregoes, hasQuoteSpan, pickInstrumentMatch } from "./span.ts";

test("formats pregão counts in pt-BR", () => {
  assert.equal(formatPregoes(null), "—");
  assert.equal(formatPregoes(undefined), "—");
  assert.equal(formatPregoes(0), "0 pregões");
  assert.equal(formatPregoes(1), "1 pregão");
  assert.equal(formatPregoes(48), "48 pregões");
});

test("hasQuoteSpan is true when any span field is present", () => {
  assert.equal(hasQuoteSpan({}), false);
  assert.equal(hasQuoteSpan({ quote_count: 0 }), false);
  assert.equal(hasQuoteSpan({ first_quote_date: "2024-01-02" }), true);
  assert.equal(hasQuoteSpan({ quote_count: 3 }), true);
});

test("pickInstrumentMatch prefers an exact identifier", () => {
  const petr = {
    instrument_id: "id-petr",
    name: "PETR4",
    asset_class: "equity",
    identifiers: ["PETR4", "BRPETRACNOR9"],
  };
  const vale = {
    instrument_id: "id-vale",
    name: "VALE3",
    asset_class: "equity",
    identifiers: ["VALE3"],
  };
  assert.equal(pickInstrumentMatch([petr, vale], "PETR4")?.instrument_id, "id-petr");
  assert.equal(pickInstrumentMatch([petr, vale], "id-vale")?.instrument_id, "id-vale");
  assert.equal(pickInstrumentMatch([petr, vale], "missing"), null);
});
