import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_HISTORY_RANGE_KEY,
  addUtcMonths,
  addUtcYears,
  defaultChartRange,
  defaultHistoryRange,
  rangeFromKey,
  rangeFromQuoteSpan,
  todayIso,
} from "./dates.ts";

test("chart and quote history default to the máx chip", () => {
  assert.equal(DEFAULT_HISTORY_RANGE_KEY, "max");
});

test("máx without quote_span is the current unbounded window", () => {
  const range = rangeFromKey("max");
  assert.equal(range.start, "");
  assert.equal(range.end, todayIso());
  assert.deepEqual(defaultChartRange(), range);
});

test("máx uses instrument quote_span first/last when the API provides both", () => {
  const span = {
    first_quote_date: "2024-01-02",
    last_quote_date: "2026-05-06",
    quote_count: 48,
  };
  assert.deepEqual(rangeFromQuoteSpan(span), { start: "2024-01-02", end: "2026-05-06" });
  assert.deepEqual(rangeFromKey("max", span), { start: "2024-01-02", end: "2026-05-06" });
  assert.deepEqual(defaultChartRange(span), { start: "2024-01-02", end: "2026-05-06" });
});

test("máx with only first_quote_date keeps today as end", () => {
  const range = rangeFromKey("max", { first_quote_date: "2024-01-02" });
  assert.equal(range.start, "2024-01-02");
  assert.equal(range.end, todayIso());
});

test("1M, 1A and 5A stay relative to today and ignore quote_span", () => {
  const today = todayIso();
  const span = { first_quote_date: "2024-01-02", last_quote_date: "2026-05-06" };
  assert.deepEqual(rangeFromKey("1M", span), { start: addUtcMonths(today, -1), end: today });
  assert.deepEqual(rangeFromKey("1A", span), { start: addUtcYears(today, -1), end: today });
  assert.deepEqual(rangeFromKey("5A", span), { start: defaultHistoryRange(5).start, end: today });
});
