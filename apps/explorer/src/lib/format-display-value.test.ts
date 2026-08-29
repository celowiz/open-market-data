import assert from "node:assert/strict";
import { test } from "node:test";

import { formatDisplayValue } from "./format-display-value.ts";

test("LAST equity price keeps two fraction digits and drops API padding", () => {
  assert.equal(formatDisplayValue("42.1100000000000000", { priceType: "LAST" }), "42.11");
  assert.equal(formatDisplayValue("32.5100000000000000", { priceType: "LAST" }), "32.51");
  assert.equal(formatDisplayValue("42.1", { priceType: "LAST" }), "42.10");
  assert.equal(formatDisplayValue("42", { priceType: "LAST" }), "42.00");
});

test("LAST rounds half up without a Number() round-trip", () => {
  assert.equal(formatDisplayValue("42.115", { priceType: "LAST" }), "42.12");
  assert.equal(formatDisplayValue("42.114", { priceType: "LAST" }), "42.11");
  assert.equal(formatDisplayValue("99.996", { priceType: "LAST" }), "100.00");
});

test("OFFICIAL_SETTLEMENT and FUND_NAV use two fraction digits", () => {
  assert.equal(
    formatDisplayValue("89656.5300000000000000", { priceType: "OFFICIAL_SETTLEMENT" }),
    "89656.53",
  );
  assert.equal(formatDisplayValue("1.2345600000000000", { priceType: "FUND_NAV" }), "1.23");
  assert.equal(formatDisplayValue("42.1100000000000000", { priceType: "CLOSE" }), "42.11");
});

test("Tesouro PU keeps up to six digits and strips trailing zeros", () => {
  assert.equal(formatDisplayValue("731.0900000000000000", { priceType: "PU_BASE" }), "731.09");
  assert.equal(formatDisplayValue("123.456789", { priceType: "BID_PU" }), "123.456789");
  assert.equal(formatDisplayValue("123.4567891", { priceType: "ASK_PU" }), "123.456789");
  assert.equal(formatDisplayValue("100.000000", { priceType: "PU_BASE" }), "100");
});

test("YIELD and INDICATIVE use 2–4 fraction digits and strip extras", () => {
  assert.equal(formatDisplayValue("14.3400000000000000", { priceType: "INDICATIVE" }), "14.34");
  assert.equal(formatDisplayValue("14.2200000000000000", { priceType: "YIELD" }), "14.22");
  assert.equal(formatDisplayValue("5.51230", { priceType: "YIELD" }), "5.5123");
  assert.equal(formatDisplayValue("5.5", { priceType: "YIELD" }), "5.50");
});

test("series observations strip padding but keep meaningful digits", () => {
  assert.equal(
    formatDisplayValue("0.0516600000000000", { kind: "series", unit: "percent_per_day" }),
    "0.05166",
  );
  assert.equal(
    formatDisplayValue("5.1512000000000000", { kind: "series", unit: "BRL_per_USD" }),
    "5.1512",
  );
  assert.equal(
    formatDisplayValue("0.12345678901234567890", { kind: "series", unit: "percent_per_day" }),
    "0.1234567890123456789",
  );
  assert.notEqual(
    formatDisplayValue("0.12345678901234567890", { kind: "series" }),
    String(Number("0.12345678901234567890")),
  );
});

test("nullish values render as an em dash and invalid strings stay as returned", () => {
  assert.equal(formatDisplayValue(null), "—");
  assert.equal(formatDisplayValue(undefined), "—");
  assert.equal(formatDisplayValue(""), "—");
  assert.equal(formatDisplayValue("n/a", { priceType: "LAST" }), "n/a");
});

test("does not mutate the raw input string", () => {
  const raw = "42.1100000000000000";
  formatDisplayValue(raw, { priceType: "LAST" });
  assert.equal(raw, "42.1100000000000000");
});
