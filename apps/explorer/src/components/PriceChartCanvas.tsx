"use client";

import {
  ColorType,
  CrosshairMode,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type Time,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  formatChartTick,
  formatChartTime,
  rawByDate,
  timeToIsoDay,
  toLineSeriesData,
  type ChartRow,
  type ChartSeries,
} from "@/lib/chart-data";
import { formatDisplayValue } from "@/lib/format-display-value";
import { cn } from "@/lib/ui";

export type { ChartRow, ChartSeries };

const ACCENT = "#d2ff3f";
const MUTED = "#9a9ba8";
const GRID = "#2a2b35";
const CANVAS = "#070709";
const ELEVATED = "#18191f";
const DEFAULT_COLORS = [ACCENT, "#7dd3fc", "#f0abfc", "#fcd34d", "#fb7185"];

function decimalString(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }
  const asString = value.toString();
  if (!asString.includes("e") && !asString.includes("E")) {
    return asString;
  }
  return value.toFixed(18).replace(/0+$/, "").replace(/\.$/, "");
}

function toChartData(points: ReturnType<typeof toLineSeriesData>): Array<LineData<Time> | WhitespaceData<Time>> {
  return points.map((point) =>
    "value" in point ? { time: point.time, value: point.value } : { time: point.time },
  );
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  return reduced;
}

type HoverItem = {
  label: string;
  text: string;
};

type HoverState = {
  dateLabel: string;
  x: number;
  y: number;
  items: HoverItem[];
};

export function PriceChartCanvas({
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<Array<ISeriesApi<"Line">>>([]);
  const preparedRef = useRef(prepared);
  const [hover, setHover] = useState<HoverState | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  const resolved = useMemo<ChartSeries[]>(() => {
    if (series && series.length > 0) {
      return series;
    }
    return [{ key: "value", label, rows: rows ?? [], priceType, unit, kind }];
  }, [kind, label, priceType, rows, series, unit]);

  const prepared = useMemo(
    () =>
      resolved.map((item) => ({
        item,
        data: toChartData(toLineSeriesData(item.rows)),
        raw: rawByDate(item.rows),
      })),
    [resolved],
  );

  preparedRef.current = prepared;

  const hasAny = prepared.some((entry) => entry.data.some((point) => "value" in point));
  const hero = variant === "hero";
  const chartIdentity = prepared
    .map(({ item }) => [item.key, item.color, item.priceType, item.unit, item.kind, item.label].join(":"))
    .concat(variant, reducedMotion ? "reduced" : "motion")
    .join("|");

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !hasAny) {
      return;
    }

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: CANVAS },
        textColor: MUTED,
        fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: GRID, style: LineStyle.Solid, visible: true },
        horzLines: { color: GRID, style: LineStyle.Solid, visible: true },
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: MUTED,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: ELEVATED,
        },
        horzLine: {
          color: MUTED,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: ELEVATED,
        },
      },
      rightPriceScale: {
        borderVisible: false,
        borderColor: GRID,
      },
      timeScale: {
        borderVisible: false,
        borderColor: GRID,
        timeVisible: false,
        tickMarkFormatter: (time) => formatChartTick(time),
      },
      localization: {
        locale: "pt-BR",
        timeFormatter: (time) => formatChartTime(time),
      },
      handleScroll: reducedMotion
        ? { mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false }
        : true,
      handleScale: reducedMotion ? { mouseWheel: false, pinch: false, axisPressedMouseMove: false } : true,
      kineticScroll: { mouse: false, touch: !reducedMotion },
    });

    const created = preparedRef.current.map(({ item }, index) =>
      chart.addSeries(LineSeries, {
        color: item.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length],
        lineWidth: 2,
        title: item.label,
        lastValueVisible: true,
        priceLineVisible: true,
        priceFormat: {
          type: "custom",
          minMove: 0.000001,
          formatter: (price) =>
            formatDisplayValue(decimalString(price), {
              priceType: item.priceType,
              unit: item.unit,
              kind: item.kind,
            }),
        },
      }),
    );

    chartRef.current = chart;
    seriesRefs.current = created;

    const onMove = (param: MouseEventParams<Time>) => {
      if (param.time === undefined || !param.point) {
        setHover(null);
        return;
      }
      const iso = timeToIsoDay(param.time);
      const items: HoverItem[] = [];
      preparedRef.current.forEach((entry, index) => {
        const seriesApi = created[index];
        const point = seriesApi ? param.seriesData.get(seriesApi) : undefined;
        if (!point || !("value" in point)) {
          return;
        }
        const raw = iso ? entry.raw.get(iso) : undefined;
        items.push({
          label: entry.item.label,
          text: formatDisplayValue(raw ?? decimalString(point.value), {
            priceType: entry.item.priceType,
            unit: entry.item.unit,
            kind: entry.item.kind,
          }),
        });
      });
      if (items.length === 0) {
        setHover(null);
        return;
      }
      setHover({
        dateLabel: formatChartTime(param.time),
        x: param.point.x,
        y: param.point.y,
        items,
      });
    };

    chart.subscribeCrosshairMove(onMove);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      seriesRefs.current = [];
      chartRef.current = null;
      setHover(null);
      chart.remove();
    };
  }, [chartIdentity, hasAny, reducedMotion]);

  useEffect(() => {
    const chart = chartRef.current;
    const seriesApis = seriesRefs.current;
    if (!chart || seriesApis.length === 0) {
      return;
    }
    prepared.forEach((entry, index) => {
      seriesApis[index]?.setData(entry.data);
    });
    chart.timeScale().fitContent();
  }, [prepared, chartIdentity]);

  if (!hasAny) {
    return null;
  }

  return (
    <div
      className={cn(
        "relative w-full",
        hero ? "h-[18rem] sm:h-[24rem] lg:h-[28rem]" : "h-64 rounded-2xl border border-border bg-surface p-2 sm:h-80",
      )}
    >
      <div ref={containerRef} className="h-full w-full" />
      {hover ? (
        <div
          className="pointer-events-none absolute z-10 rounded-xl border border-border bg-elevated px-3 py-2 shadow-lg"
          style={{
            left: Math.min(hover.x + 12, (containerRef.current?.clientWidth ?? 320) - 160),
            top: Math.max(hover.y - 48, 8),
          }}
        >
          <p className="font-mono text-xs text-muted">{hover.dateLabel}</p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {hover.items.map((item) => (
              <li key={item.label} className="font-mono text-sm tabular-nums text-foreground">
                <span className="mr-2 text-muted">{item.label}</span>
                {item.text}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
