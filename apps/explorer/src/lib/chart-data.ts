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

export type LineSeriesValuePoint = {
  time: string;
  value: number;
};

export type LineSeriesWhitespacePoint = {
  time: string;
};

export type LineSeriesPoint = LineSeriesValuePoint | LineSeriesWhitespacePoint;

export type ChartTime =
  | string
  | number
  | {
      year: number;
      month: number;
      day: number;
    };

const SAO_PAULO = "America/Sao_Paulo";
const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

function addUtcDays(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

function utcDayDiff(start: string, end: string): number {
  const from = Date.parse(`${start}T00:00:00Z`);
  const to = Date.parse(`${end}T00:00:00Z`);
  return Math.round((to - from) / 86_400_000);
}

export function isWhitespacePoint(point: LineSeriesPoint): point is LineSeriesWhitespacePoint {
  return !("value" in point);
}

function parseIsoDay(date: string): { year: number; month: number; day: number } | null {
  const match = ISO_DAY.exec(date);
  if (!match) {
    return null;
  }
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  };
}

function toIsoDay(parts: { year: number; month: number; day: number }): string {
  const month = String(parts.month).padStart(2, "0");
  const day = String(parts.day).padStart(2, "0");
  return `${parts.year}-${month}-${day}`;
}

function uniqueSortedValues(rows: ChartRow[]): LineSeriesValuePoint[] {
  const latest = new Map<string, number>();
  for (const row of rows) {
    const parsed = parseIsoDay(row.date);
    if (!parsed) {
      continue;
    }
    if (row.raw.trim() === "") {
      continue;
    }
    const value = Number(row.raw);
    if (!Number.isFinite(value)) {
      continue;
    }
    latest.set(toIsoDay(parsed), value);
  }
  return [...latest.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([time, value]) => ({ time, value }));
}

function fillCalendarGaps(points: LineSeriesValuePoint[]): LineSeriesPoint[] {
  const out: LineSeriesPoint[] = [];
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    if (index > 0) {
      const previous = points[index - 1];
      const gap = utcDayDiff(previous.time, current.time);
      for (let offset = 1; offset < gap; offset += 1) {
        out.push({ time: addUtcDays(previous.time, offset) });
      }
    }
    out.push(current);
  }
  return out;
}

export function toLineSeriesData(rows: ChartRow[]): LineSeriesPoint[] {
  return fillCalendarGaps(uniqueSortedValues(rows));
}

function businessDayDate(time: ChartTime): Date | null {
  if (typeof time === "string") {
    const parsed = parseIsoDay(time);
    if (!parsed) {
      return null;
    }
    return new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day, 12));
  }
  if (typeof time === "number") {
    return new Date(time * 1000);
  }
  if (time && typeof time === "object" && "year" in time) {
    return new Date(Date.UTC(time.year, time.month - 1, time.day, 12));
  }
  return null;
}

export function formatChartTime(time: ChartTime): string {
  const date = businessDayDate(time);
  if (!date) {
    return String(time);
  }
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: SAO_PAULO,
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function timeToIsoDay(time: ChartTime): string | null {
  if (typeof time === "string") {
    const parsed = parseIsoDay(time);
    return parsed ? toIsoDay(parsed) : null;
  }
  if (typeof time === "number") {
    return null;
  }
  if (time && typeof time === "object" && "year" in time) {
    return toIsoDay(time);
  }
  return null;
}

export function formatChartTick(time: ChartTime): string {
  const date = businessDayDate(time);
  if (!date) {
    return String(time);
  }
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: SAO_PAULO,
    day: "2-digit",
    month: "short",
  }).format(date);
}

export function rawByDate(rows: ChartRow[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const row of rows) {
    const parsed = parseIsoDay(row.date);
    if (!parsed) {
      continue;
    }
    map.set(toIsoDay(parsed), row.raw);
  }
  return map;
}
