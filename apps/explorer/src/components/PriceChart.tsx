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
import { cn } from "@/lib/ui";

export type { ChartRow, ChartSeries };

const ACCENT = "#d2ff3f";
const MUTED = "#9a9ba8";
const GRID = "#2a2b35";
const DEFAULT_COLORS = [ACCENT, "#7dd3fc", "#f0abfc", "#fcd34d", "#fb7185"];

type TooltipEntry = {
  name?: string;
  payload?: { date?: string };
};

function ChartTooltip({
  active,
  payload,
  label,
  series,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  series: ChartSeries[];
}) {
  if (!active || !payload?.length) {
    return null;
  }
  const date = String(label ?? payload[0]?.payload?.date ?? "");
  if (isGapMarkerDate(date)) {
    return null;
  }
  return (
    <div className="rounded-xl border border-border bg-elevated px-3 py-2 shadow-lg">
      <p className="font-mono text-xs text-muted">{date}</p>
      <ul className="mt-1 flex flex-col gap-0.5">
        {payload.map((item, index) => {
          const match =
            series.find((entry) => entry.key === item.name) ??
            series.find((entry) => entry.label === item.name) ??
            series[index];
          const raw = date ? match?.rows.find((row) => row.date === date)?.raw : undefined;
          return (
            <li key={`${item.name}-${index}`} className="font-mono text-sm tabular-nums text-foreground">
              <span className="mr-2 text-muted">{match?.label ?? String(item.name)}</span>
              {formatDisplayValue(raw ?? "", {
                priceType: match?.priceType,
                unit: match?.unit,
                kind: match?.kind,
              })}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function PriceChart({
  rows,
  label = "Valor",
  series,
  priceType,
  unit,
  kind,
  variant = "panel",
}: {
  rows?: ChartRow[];
  label?: string;
  series?: ChartSeries[];
  priceType?: string | null;
  unit?: string | null;
  kind?: "quote" | "series";
  variant?: "hero" | "panel";
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

  const hero = variant === "hero";

  return (
    <div
      className={cn(
        "w-full",
        hero ? "h-[18rem] sm:h-[24rem] lg:h-[28rem]" : "h-64 rounded-2xl border border-border bg-surface p-2 sm:h-80",
      )}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis
            dataKey="date"
            type="category"
            scale="point"
            padding={{ left: 8, right: 8 }}
            tick={{ fontSize: 11, fill: MUTED }}
            axisLine={false}
            tickLine={false}
            minTickGap={24}
            tickFormatter={(value) => (isGapMarkerDate(String(value)) ? "—" : String(value))}
          />
          <YAxis
            tick={{ fontSize: 11, fill: MUTED }}
            width={64}
            domain={["auto", "auto"]}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<ChartTooltip series={resolved} />}
            cursor={{ stroke: MUTED, strokeWidth: 1, strokeDasharray: "4 4" }}
          />
          {resolved.map((item, index) => (
            <Line
              key={item.key}
              type="linear"
              dataKey={item.key}
              name={item.label}
              stroke={item.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
              strokeWidth={hero ? 2.25 : 2}
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
