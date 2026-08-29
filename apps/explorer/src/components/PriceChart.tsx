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

import {
  buildChartData,
  isGapMarkerDate,
  type ChartRow,
  type ChartSeries,
} from "@/lib/chart-data";
import { formatDisplayValue } from "@/lib/format-display-value";

export type { ChartRow, ChartSeries };

const DEFAULT_COLORS = ["#0f766e", "#1e293b", "#b45309", "#3730a3", "#9f1239"];

export function PriceChart({
  rows,
  label = "Valor",
  series,
  priceType,
  unit,
  kind,
}: {
  rows?: ChartRow[];
  label?: string;
  series?: ChartSeries[];
  priceType?: string | null;
  unit?: string | null;
  kind?: "quote" | "series";
}) {
  const resolved = useMemo<ChartSeries[]>(() => {
    if (series && series.length > 0) {
      return series;
    }
    return [{ key: "value", label, rows: rows ?? [], priceType, unit, kind }];
  }, [kind, label, priceType, rows, series, unit]);

  const data = useMemo(() => buildChartData(resolved), [resolved]);

  const hasAny = data.some((row) => resolved.some((item) => typeof row[item.key] === "number"));
  if (!hasAny) {
    return null;
  }

  return (
    <div className="h-72 w-full rounded-lg border border-slate-200 bg-white p-2 sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            type="category"
            scale="point"
            padding={{ left: 16, right: 16 }}
            tick={{ fontSize: 11 }}
            minTickGap={24}
            tickFormatter={(value) => (isGapMarkerDate(String(value)) ? "—" : String(value))}
          />
          <YAxis tick={{ fontSize: 11 }} width={72} domain={["auto", "auto"]} />
          <Tooltip
            formatter={(value, name, item) => {
              const date = (item as { payload?: { date?: string } }).payload?.date;
              const match =
                resolved.find((entry) => entry.key === name) ??
                resolved.find((entry) => entry.label === name);
              const raw = date ? match?.rows.find((row) => row.date === date)?.raw : undefined;
              return [
                formatDisplayValue(raw ?? String(value), {
                  priceType: match?.priceType,
                  unit: match?.unit,
                  kind: match?.kind,
                }),
                match?.label ?? String(name),
              ];
            }}
            labelFormatter={(date) => (isGapMarkerDate(String(date)) ? "—" : String(date))}
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
