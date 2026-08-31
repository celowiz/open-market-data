export type WindowPoint = {
  date: string;
  raw: string;
};

export type WindowDelta = {
  firstRaw: string;
  lastRaw: string;
  firstDate: string;
  lastDate: string;
  direction: "up" | "down" | "flat";
  pctChange: number | null;
};

export function windowDeltaFromRows(rows: WindowPoint[]): WindowDelta | null {
  const sorted = [...rows]
    .filter((row) => row.raw.trim() !== "")
    .sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length < 2) {
    return null;
  }
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const start = Number(first.raw);
  const end = Number(last.raw);
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return null;
  }
  const diff = end - start;
  const direction: WindowDelta["direction"] = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  const pctChange = start === 0 ? null : (diff / start) * 100;
  return {
    firstRaw: first.raw,
    lastRaw: last.raw,
    firstDate: first.date,
    lastDate: last.date,
    direction,
    pctChange,
  };
}

export function formatPctChange(pct: number): string {
  const abs = Math.abs(pct);
  const body = (Math.round(abs * 100) / 100).toFixed(2).replace(".", ",");
  if (pct > 0) {
    return `+${body}%`;
  }
  if (pct < 0) {
    return `−${body}%`;
  }
  return `${body}%`;
}

export function sparklineValues(rows: WindowPoint[]): number[] {
  const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
  const values: number[] = [];
  for (const row of sorted) {
    const value = Number(row.raw);
    if (Number.isFinite(value)) {
      values.push(value);
    }
  }
  return values;
}
