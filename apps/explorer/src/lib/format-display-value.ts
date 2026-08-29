export type DisplayFormatKind = "quote" | "series" | "coverage";

export type DisplayFormatContext = {
  priceType?: string | null;
  unit?: string | null;
  kind?: DisplayFormatKind;
};

const TWO_DIGIT_PRICE_TYPES = new Set([
  "LAST",
  "LAST_TRADE",
  "CLOSE",
  "OFFICIAL_SETTLEMENT",
  "FUND_NAV",
]);

const TESOURO_PU_PRICE_TYPES = new Set(["PU_BASE", "BID_PU", "ASK_PU"]);
const YIELD_PRICE_TYPES = new Set(["YIELD", "INDICATIVE"]);

type DecimalParts = {
  sign: string;
  int: string;
  frac: string;
};

function parseDecimal(raw: string): DecimalParts | null {
  const match = raw.match(/^([+-])?(\d+)(?:\.(\d*))?$/);
  if (!match) {
    return null;
  }
  const sign = match[1] === "-" ? "-" : "";
  const int = match[2].replace(/^0+(?=\d)/, "") || "0";
  const frac = match[3] ?? "";
  return { sign, int, frac };
}

function roundTo(int: string, frac: string, maxFrac: number): { int: string; frac: string } {
  if (!Number.isFinite(maxFrac) || frac.length <= maxFrac) {
    return { int, frac };
  }
  if (maxFrac === 0) {
    if ((frac[0] ?? "0") < "5") {
      return { int, frac: "" };
    }
    return { int: (BigInt(int) + 1n).toString(), frac: "" };
  }
  const head = frac.slice(0, maxFrac);
  const discarded = frac.slice(maxFrac);
  if ((discarded[0] ?? "0") < "5") {
    return { int, frac: head };
  }
  const digits = `${int}${head}`;
  const incremented = (BigInt(digits) + 1n).toString();
  if (incremented.length > digits.length) {
    return {
      int: incremented.slice(0, incremented.length - maxFrac),
      frac: incremented.slice(incremented.length - maxFrac),
    };
  }
  return {
    int: incremented.slice(0, incremented.length - maxFrac) || "0",
    frac: incremented.slice(incremented.length - maxFrac),
  };
}

function joinDecimal(
  sign: string,
  int: string,
  frac: string,
  options: { minFrac: number; stripZeros: boolean },
): string {
  let nextFrac = frac;
  if (options.stripZeros) {
    nextFrac = nextFrac.replace(/0+$/, "");
  }
  if (options.minFrac > 0) {
    nextFrac = nextFrac.padEnd(options.minFrac, "0");
  }
  if (nextFrac.length === 0) {
    return `${sign}${int}`;
  }
  return `${sign}${int}.${nextFrac}`;
}

export function formatDisplayValue(
  raw: string | null | undefined,
  context?: DisplayFormatContext,
): string {
  if (raw == null) {
    return "—";
  }
  const trimmed = raw.trim();
  if (trimmed === "") {
    return "—";
  }
  const parsed = parseDecimal(trimmed);
  if (!parsed) {
    return trimmed;
  }

  const priceType = context?.priceType?.trim().toUpperCase() ?? "";
  const kind = context?.kind;

  if (kind === "series") {
    return joinDecimal(parsed.sign, parsed.int, parsed.frac, { minFrac: 0, stripZeros: true });
  }
  if (TWO_DIGIT_PRICE_TYPES.has(priceType)) {
    const rounded = roundTo(parsed.int, parsed.frac, 2);
    return joinDecimal(parsed.sign, rounded.int, rounded.frac, { minFrac: 2, stripZeros: false });
  }
  if (TESOURO_PU_PRICE_TYPES.has(priceType)) {
    const rounded = roundTo(parsed.int, parsed.frac, 6);
    return joinDecimal(parsed.sign, rounded.int, rounded.frac, { minFrac: 0, stripZeros: true });
  }
  if (YIELD_PRICE_TYPES.has(priceType)) {
    const rounded = roundTo(parsed.int, parsed.frac, 4);
    return joinDecimal(parsed.sign, rounded.int, rounded.frac, { minFrac: 2, stripZeros: true });
  }
  return joinDecimal(parsed.sign, parsed.int, parsed.frac, { minFrac: 0, stripZeros: true });
}
