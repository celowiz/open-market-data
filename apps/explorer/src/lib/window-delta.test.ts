import assert from "node:assert/strict";
import { test } from "node:test";

import {
  formatPctChange,
  sparklineValues,
  windowDeltaFromRows,
} from "./window-delta.ts";

test("delta uses first and last prints in the loaded window only", () => {
  const delta = windowDeltaFromRows([
    { date: "2026-08-10", raw: "10.00" },
    { date: "2026-08-11", raw: "12.50" },
    { date: "2026-08-12", raw: "11.00" },
  ]);
  assert.ok(delta);
  assert.equal(delta.firstRaw, "10.00");
  assert.equal(delta.lastRaw, "11.00");
  assert.equal(delta.direction, "up");
  assert.ok(delta.pctChange !== null);
  assert.equal(Math.round((delta.pctChange ?? 0) * 100) / 100, 10);
});

test("a single print does not invent a delta", () => {
  assert.equal(windowDeltaFromRows([{ date: "2026-08-10", raw: "10.00" }]), null);
  assert.equal(windowDeltaFromRows([]), null);
});

test("down windows are red-direction and empty raw is ignored", () => {
  const delta = windowDeltaFromRows([
    { date: "2026-08-12", raw: "8" },
    { date: "2026-08-10", raw: "10" },
    { date: "2026-08-11", raw: "   " },
  ]);
  assert.ok(delta);
  assert.equal(delta.firstDate, "2026-08-10");
  assert.equal(delta.lastDate, "2026-08-12");
  assert.equal(delta.direction, "down");
});

test("formatPctChange uses a display minus and never fabricates a print", () => {
  assert.equal(formatPctChange(2.4), "+2,40%");
  assert.equal(formatPctChange(-1.5), "−1,50%");
  assert.equal(formatPctChange(0), "0,00%");
});

test("sparkline values skip non-numeric raw prints", () => {
  assert.deepEqual(
    sparklineValues([
      { date: "2026-08-11", raw: "2" },
      { date: "2026-08-10", raw: "1" },
      { date: "2026-08-12", raw: "not-a-price" },
    ]),
    [1, 2],
  );
});
