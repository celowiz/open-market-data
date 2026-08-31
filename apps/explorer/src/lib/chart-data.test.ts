import assert from "node:assert/strict";
import { test } from "node:test";

import { utcDayDiff } from "./dates.ts";
import {
  formatChartTick,
  formatChartTime,
  isWhitespacePoint,
  timeToIsoDay,
  toLineSeriesData,
} from "./chart-data.ts";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function times(rows: ReturnType<typeof toLineSeriesData>): string[] {
  return rows.map((row) => row.time);
}

test("Fri→Mon weekend inserts Saturday/Sunday whitespace, never value: null", () => {
  assert.equal(utcDayDiff("2026-08-21", "2026-08-24"), 3);
  const data = toLineSeriesData([
    { date: "2026-08-24", raw: "42.1100000000000000" },
    { date: "2026-08-21", raw: "32.5100000000000000" },
  ]);
  assert.deepEqual(times(data), ["2026-08-21", "2026-08-22", "2026-08-23", "2026-08-24"]);
  assert.equal("value" in data[0] ? data[0].value : undefined, 32.51);
  assert.ok(isWhitespacePoint(data[1]));
  assert.ok(isWhitespacePoint(data[2]));
  assert.equal("value" in data[3] ? data[3].value : undefined, 42.11);
  assert.ok(data.every((point) => ISO_DAY.test(point.time)));
  assert.ok(data.every((point) => !("value" in point) || typeof point.value === "number"));
  assert.ok(!data.some((point) => "value" in point && point.value === null));
});

test("holiday-length gaps up to 7 calendar days use whitespace days, not dummy prints", () => {
  assert.equal(utcDayDiff("2026-08-20", "2026-08-24"), 4);
  assert.equal(utcDayDiff("2026-08-17", "2026-08-24"), 7);
  for (const [start, end] of [
    ["2026-08-20", "2026-08-24"],
    ["2026-08-17", "2026-08-24"],
  ] as const) {
    const data = toLineSeriesData([
      { date: start, raw: "1.00" },
      { date: end, raw: "2.00" },
    ]);
    assert.equal(data[0]?.time, start);
    assert.equal(data[data.length - 1]?.time, end);
    assert.equal(utcDayDiff(start, end) + 1, data.length);
    const middle = data.slice(1, -1);
    assert.ok(middle.length > 0);
    assert.ok(middle.every(isWhitespacePoint));
    assert.ok(!data.some((point) => "value" in point && point.value === null));
  }
});

test("true outage (utcDayDiff > 7) fills the calendar with whitespace, not null values", () => {
  assert.equal(utcDayDiff("2026-08-16", "2026-08-24"), 8);
  const data = toLineSeriesData([
    { date: "2026-08-16", raw: "1.00" },
    { date: "2026-08-24", raw: "2.00" },
  ]);
  assert.equal(data.length, 9);
  assert.equal(data[0]?.time, "2026-08-16");
  assert.equal("value" in data[0] ? data[0].value : undefined, 1);
  assert.ok(isWhitespacePoint(data[1]));
  assert.equal(data[1]?.time, "2026-08-17");
  assert.ok(!("value" in data[1]));
  assert.equal(data[data.length - 1]?.time, "2026-08-24");
  assert.ok(data.every((point) => ISO_DAY.test(point.time)));
});

test("series times are unique, strictly ascending BusinessDays", () => {
  const data = toLineSeriesData([
    { date: "2026-01-03", raw: "3" },
    { date: "2026-01-01", raw: "1" },
    { date: "2026-01-01", raw: "1.5" },
    { date: "2026-01-03", raw: "4" },
  ]);
  const valueTimes = data.filter((point) => "value" in point).map((point) => point.time);
  assert.deepEqual(valueTimes, ["2026-01-01", "2026-01-03"]);
  assert.equal("value" in data[0] ? data[0].value : undefined, 1.5);
  assert.equal("value" in data[data.length - 1] ? data[data.length - 1].value : undefined, 4);
  for (let index = 1; index < data.length; index += 1) {
    assert.ok(data[index].time > data[index - 1].time);
  }
  assert.equal(new Set(times(data)).size, data.length);
});

test("non-numeric raw prints are skipped, never fabricated", () => {
  const data = toLineSeriesData([
    { date: "2026-01-01", raw: "n/a" },
    { date: "2026-01-02", raw: "10" },
    { date: "2026-01-03", raw: "" },
  ]);
  assert.deepEqual(
    data.filter((point) => "value" in point),
    [{ time: "2026-01-02", value: 10 }],
  );
});

test("BusinessDay tick stays on the calendar date in America/Sao_Paulo", () => {
  const label = formatChartTime("2026-08-21");
  assert.match(label, /^21\b/);
  assert.doesNotMatch(label, /^20\b/);
  assert.equal(formatChartTime({ year: 2026, month: 8, day: 21 }), label);
  assert.match(formatChartTick("2026-08-21"), /^21\b/);
  assert.equal(timeToIsoDay("2026-08-21"), "2026-08-21");
  assert.equal(timeToIsoDay({ year: 2026, month: 8, day: 21 }), "2026-08-21");
  assert.equal(timeToIsoDay(1_724_198_400), null);
});
