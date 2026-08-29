import assert from "node:assert/strict";
import { test } from "node:test";

import { utcDayDiff } from "./dates.ts";
import { buildChartData, isGapMarkerDate } from "./chart-data.ts";

test("Fri→Mon weekend (utcDayDiff=3) stays two observation dates with no null", () => {
  assert.equal(utcDayDiff("2026-08-21", "2026-08-24"), 3);
  const data = buildChartData([
    {
      key: "value",
      label: "LAST",
      rows: [
        { date: "2026-08-24", raw: "42.1100000000000000" },
        { date: "2026-08-21", raw: "32.5100000000000000" },
      ],
    },
  ]);
  assert.deepEqual(
    data.map((row) => row.date),
    ["2026-08-21", "2026-08-24"],
  );
  assert.equal(typeof data[0]?.value, "number");
  assert.equal(typeof data[1]?.value, "number");
  assert.ok(data.every((row) => row.value !== null));
  assert.ok(!data.some((row) => typeof row.date === "string" && isGapMarkerDate(row.date)));
  assert.ok(!data.some((row) => row.date === "2026-08-22" || row.date === "2026-08-23"));
});

test("holiday-length gaps up to 7 calendar days do not insert a break", () => {
  assert.equal(utcDayDiff("2026-08-20", "2026-08-24"), 4);
  assert.equal(utcDayDiff("2026-08-17", "2026-08-24"), 7);
  for (const [start, end] of [
    ["2026-08-20", "2026-08-24"],
    ["2026-08-17", "2026-08-24"],
  ] as const) {
    const data = buildChartData([
      {
        key: "value",
        label: "LAST",
        rows: [
          { date: start, raw: "1.00" },
          { date: end, raw: "2.00" },
        ],
      },
    ]);
    assert.deepEqual(
      data.map((row) => row.date),
      [start, end],
    );
    assert.ok(data.every((row) => row.value !== null));
  }
});

test("true outage (utcDayDiff > 7) inserts a break marker, not a dummy calendar day", () => {
  assert.equal(utcDayDiff("2026-08-16", "2026-08-24"), 8);
  const data = buildChartData([
    {
      key: "value",
      label: "LAST",
      rows: [
        { date: "2026-08-16", raw: "1.00" },
        { date: "2026-08-24", raw: "2.00" },
      ],
    },
  ]);
  assert.equal(data.length, 3);
  assert.equal(data[0]?.date, "2026-08-16");
  assert.equal(data[0]?.value, 1);
  assert.equal(data[1]?.value, null);
  assert.ok(typeof data[1]?.date === "string" && isGapMarkerDate(data[1].date));
  assert.equal(data[2]?.date, "2026-08-24");
  assert.ok(!data.some((row) => row.date === "2026-08-17"));
});

test("overlay extra dates leave the other series undefined, not null", () => {
  const data = buildChartData([
    {
      key: "a",
      label: "A",
      rows: [
        { date: "2026-01-01", raw: "1" },
        { date: "2026-01-02", raw: "2" },
      ],
    },
    {
      key: "b",
      label: "B",
      rows: [
        { date: "2026-01-01", raw: "3" },
        { date: "2026-01-03", raw: "4" },
      ],
    },
  ]);
  const byDate = Object.fromEntries(data.map((row) => [row.date, row]));
  assert.equal(byDate["2026-01-01"]?.a, 1);
  assert.equal(byDate["2026-01-01"]?.b, 3);
  assert.equal(byDate["2026-01-02"]?.a, 2);
  assert.equal(byDate["2026-01-02"]?.b, undefined);
  assert.ok(!Object.hasOwn(byDate["2026-01-02"] ?? {}, "b"));
  assert.equal(byDate["2026-01-03"]?.b, 4);
  assert.equal(byDate["2026-01-03"]?.a, undefined);
  assert.ok(!Object.hasOwn(byDate["2026-01-03"] ?? {}, "a"));
});
