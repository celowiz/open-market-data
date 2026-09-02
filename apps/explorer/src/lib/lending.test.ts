import assert from "node:assert/strict";
import test from "node:test";

import { hasLendingData, latestLendingSnapshot } from "./lending.ts";
import type { LendingSnapshotResponse } from "./types.ts";

const petr4: LendingSnapshotResponse = {
  ticker: "PETR4",
  date: "2026-08-21",
  snapshot_type: "open_position",
  qty: "12000000",
  avg_rate: "0.12",
  contracts: 42,
  avg_price: "38.5",
  balance_brl: null,
  market: "Neg. Eletrônica D+0",
  source: "b3",
};

test("latestLendingSnapshot picks the newest open_position row", () => {
  const older = { ...petr4, date: "2026-08-20", qty: "1" };
  const found = latestLendingSnapshot([older, petr4], "open_position");
  assert.equal(found?.qty, "12000000");
  assert.equal(found?.avg_rate, "0.12");
});

test("hasLendingData is true for a fixture ticker snapshot", () => {
  assert.equal(hasLendingData([petr4]), true);
  assert.equal(hasLendingData([]), false);
});
