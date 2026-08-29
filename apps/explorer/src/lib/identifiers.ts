export const TESOURO_PRICE_TYPES = [
  "PU_BASE",
  "BID_PU",
  "ASK_PU",
  "YIELD",
  "INDICATIVE",
] as const;

export const TESOURO_PU_TYPES = new Set(["PU_BASE", "BID_PU", "ASK_PU"]);
export const TESOURO_YIELD_TYPES = new Set(["YIELD", "INDICATIVE"]);

export const FUTURE_PRICE_TYPES = ["OFFICIAL_SETTLEMENT", "LAST"] as const;

const TESOURO_ID_RE = /^[^:]+:\d{4}-\d{2}-\d{2}$/;
const B3_FUTURE_RE = /^(DI1|DOL|WDO|WIN|IND)[FGHJKMNQUVXZ]\d{2}$/i;

export function isTesouroIdentifier(identifier: string): boolean {
  return TESOURO_ID_RE.test(identifier.trim());
}

export function isB3FutureIdentifier(identifier: string): boolean {
  return B3_FUTURE_RE.test(identifier.trim());
}

export function defaultPriceType(identifier: string): string {
  if (isTesouroIdentifier(identifier)) {
    return "PU_BASE";
  }
  if (isB3FutureIdentifier(identifier)) {
    return "OFFICIAL_SETTLEMENT";
  }
  return "";
}

export function tesouroCompanionPriceType(priceType: string): string | null {
  if (TESOURO_PU_TYPES.has(priceType)) {
    return "YIELD";
  }
  if (TESOURO_YIELD_TYPES.has(priceType)) {
    return "PU_BASE";
  }
  return "YIELD";
}
