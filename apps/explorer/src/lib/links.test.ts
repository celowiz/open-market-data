import assert from "node:assert/strict";
import { test } from "node:test";

import { hrefForIdentifier, hrefForInstrument } from "./links.ts";

test("equity identifiers open the quotes page", () => {
  assert.equal(
    hrefForInstrument({
      instrument_id: "id-1",
      name: "Petrobras",
      asset_class: "equity",
      identifiers: ["PETR4"],
    }),
    "/quotes/PETR4",
  );
  assert.equal(hrefForIdentifier("PETR4", "equity"), "/quotes/PETR4");
});

test("fund identifiers open the funds page using CNPJ", () => {
  assert.equal(
    hrefForInstrument({
      instrument_id: "id-2",
      name: "Fundo exemplo",
      asset_class: "fund",
      identifiers: ["00017024000153"],
    }),
    "/funds/00017024000153",
  );
});

test("rate or BCB identifiers open the series page", () => {
  assert.equal(
    hrefForInstrument({
      instrument_id: "id-3",
      name: "CDI",
      asset_class: "rate",
      identifiers: ["BCB:CDI_DAILY"],
    }),
    "/series/BCB%3ACDI_DAILY",
  );
});
