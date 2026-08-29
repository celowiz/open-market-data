export type ChartRow = {
  date: string;
  raw: string;
};

export type ChartSeries = {
  key: string;
  label: string;
  color?: string;
  rows: ChartRow[];
  priceType?: string | null;
  unit?: string | null;
  kind?: "quote" | "series";
};

export type ChartPoint = Record<string, string | number | null | undefined>;

/** Break the line only for a real outage, not ordinary weekends or long weekends. */
export const OUTAGE_BREAK_DAYS = 7;
export const GAP_MARKER_SUFFIX = "~gap";

export function isGapMarkerDate(date: string): boolean {
  return date.endsWith(GAP_MARKER_SUFFIX);
}

function utcDayDiff(start: string, end: string): number {
  const from = Date.parse(`${start}T00:00:00Z`);
  const to = Date.parse(`${end}T00:00:00Z`);
  return Math.round((to - from) / 86_400_000);
}

function withOutageBreaks(rows: ChartRow[]): Array<{ date: string; raw: string | null }> {
  const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
  const out: Array<{ date: string; raw: string | null }> = [];
  for (let index = 0; index < sorted.length; index += 1) {
    const current = sorted[index];
    if (index > 0) {
      const previous = sorted[index - 1];
      if (utcDayDiff(previous.date, current.date) > OUTAGE_BREAK_DAYS) {
        out.push({ date: `${previous.date}${GAP_MARKER_SUFFIX}`, raw: null });
      }
    }
    out.push({ date: current.date, raw: current.raw });
  }
  return out;
}

export function buildChartData(series: ChartSeries[]): ChartPoint[] {
  const dates = new Set<string>();
  const byKey = new Map<string, Map<string, number | null>>();
  for (const item of series) {
    const map = new Map<string, number | null>();
    for (const row of withOutageBreaks(item.rows)) {
      dates.add(row.date);
      if (row.raw === null) {
        map.set(row.date, null);
        continue;
      }
      const value = Number(row.raw);
      if (Number.isFinite(value)) {
        map.set(row.date, value);
      }
    }
    byKey.set(item.key, map);
  }
  return [...dates]
    .sort((a, b) => a.localeCompare(b))
    .map((date) => {
      const point: ChartPoint = { date };
      for (const item of series) {
        const map = byKey.get(item.key);
        if (map?.has(date)) {
          point[item.key] = map.get(date);
        }
      }
      return point;
    });
}
