"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { addUtcDays, utcDayDiff } from "@/lib/dates";

export type ChartRow = {
  date: string;
  raw: string;
};

export type ChartSeries = {
  key: string;
  label: string;
  color?: string;
  rows: ChartRow[];
};

const DEFAULT_COLORS = ["#0f766e", "#1e293b", "#b45309", "#3730a3", "#9f1239"];
const OUTAGE_GAP_DAYS = 4;

function withGaps(rows: ChartRow[]): Array<{ date: string; raw: string | null }> {
  const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
  const out: Array<{ date: string; raw: string | null }> = [];
  for (let index = 0; index < sorted.length; index += 1) {
    const current = sorted[index];
    if (index > 0) {
      const previous = sorted[index - 1];
      if (utcDayDiff(previous.date, current.date) > OUTAGE_GAP_DAYS) {
        out.push({ date: addUtcDays(previous.date, 1), raw: null });
      }
    }
    out.push({ date: current.date, raw: current.raw });
  }
  return out;
}

export function PriceChart({
  rows,
  label = "Valor",
  series,
}: {
  rows?: ChartRow[];
  label?: string;
  series?: ChartSeries[];
}) {
  const resolved = useMemo<ChartSeries[]>(() => {
    if (series && series.length > 0) {
      return series;
    }
    return [{ key: "value", label, rows: rows ?? [] }];
  }, [label, rows, series]);

  const data = useMemo(() => {
    const dates = new Set<string>();
    const byKey = new Map<string, Map<string, number | null>>();
    for (const item of resolved) {
      const map = new Map<string, number | null>();
      for (const row of withGaps(item.rows)) {
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
        const point: Record<string, string | number | null | undefined> = { date };
        for (const item of resolved) {
          const map = byKey.get(item.key);
          if (map?.has(date)) {
            point[item.key] = map.get(date);
          }
        }
        return point;
      });
  }, [resolved]);

  const hasAny = data.some((row) => resolved.some((item) => typeof row[item.key] === "number"));
  if (!hasAny) {
    return null;
  }

  return (
    <div className="h-72 w-full rounded-lg border border-slate-200 bg-white p-2 sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 11 }} width={72} domain={["auto", "auto"]} />
          <Tooltip
            formatter={(value, name, item) => {
              const date = (item as { payload?: { date?: string } }).payload?.date;
              const match =
                resolved.find((entry) => entry.key === name) ??
                resolved.find((entry) => entry.label === name);
              const raw = match?.rows.find((row) => row.date === date)?.raw;
              return [raw ?? String(value), match?.label ?? String(name)];
            }}
            labelFormatter={(date) => String(date)}
          />
          {resolved.map((item, index) => (
            <Line
              key={item.key}
              type="linear"
              dataKey={item.key}
              name={item.label}
              stroke={item.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
