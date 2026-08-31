"use client";

import { Suspense } from "react";

import { HomeTradingView } from "@/components/HomeTradingView";
import { PageShell } from "@/components/PageShell";
import { ChartSkeleton } from "@/components/Status";

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <PageShell>
          <ChartSkeleton label="Carregando…" />
        </PageShell>
      }
    >
      <PageShell wide>
        <HomeTradingView />
      </PageShell>
    </Suspense>
  );
}
