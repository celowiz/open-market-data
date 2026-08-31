"use client";

import dynamic from "next/dynamic";

export type { ChartRow, ChartSeries } from "@/lib/chart-data";

function ChartPlaceholder() {
  return <div className="h-[18rem] w-full sm:h-[24rem]" />;
}

export const PriceChart = dynamic(
  () => import("./PriceChartCanvas").then((mod) => mod.PriceChartCanvas),
  {
    ssr: false,
    loading: () => <ChartPlaceholder />,
  },
);
