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

export type ChartRow = {
  date: string;
  raw: string;
};

function toPoints(rows: ChartRow[]): Array<{ date: string; value: number; raw: string }> {
  return rows
    .map((row) => {
      const value = Number(row.raw);
      if (!Number.isFinite(value)) {
        return null;
      }
      return { date: row.date, value, raw: row.raw };
    })
    .filter((row): row is { date: string; value: number; raw: string } => row !== null)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function PriceChart({
  rows,
  label,
}: {
  rows: ChartRow[];
  label: string;
}) {
  const data = useMemo(() => toPoints(rows), [rows]);

  if (data.length === 0) {
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
            formatter={(_value, _name, item) => {
              const raw = (item as { payload?: { raw?: string } }).payload?.raw;
              return [raw ?? String(_value), label];
            }}
            labelFormatter={(date) => String(date)}
          />
          <Line
            type="monotone"
            dataKey="value"
            name={label}
            stroke="#0f766e"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
