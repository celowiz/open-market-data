export type KnownBcbSeries = {
  code: string;
  sgs: string;
  name: string;
  unit: string;
};

export const KNOWN_BCB_SERIES: readonly KnownBcbSeries[] = [
  { code: "BCB:SELIC_DAILY", sgs: "11", name: "Selic over", unit: "percent_per_day" },
  { code: "BCB:CDI_DAILY", sgs: "12", name: "CDI", unit: "percent_per_day" },
  { code: "BCB:SELIC_TARGET", sgs: "432", name: "Selic meta", unit: "percent_per_year" },
  { code: "BCB:PTAX_USD_SELL", sgs: "1", name: "PTAX USD venda", unit: "BRL_per_USD" },
  { code: "BCB:PTAX_USD_BUY", sgs: "10813", name: "PTAX USD compra", unit: "BRL_per_USD" },
];

export const DEFAULT_COMPARE_SERIES = ["BCB:CDI_DAILY", "BCB:SELIC_DAILY"] as const;

export function knownBcbSeries(code: string): KnownBcbSeries | undefined {
  const needle = code.trim().toUpperCase();
  return KNOWN_BCB_SERIES.find(
    (item) => item.code === needle || item.sgs === code.trim() || item.code === code.trim(),
  );
}
