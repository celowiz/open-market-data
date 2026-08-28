"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { DateRangeForm, type DateRangeValue } from "@/components/DateRangeForm";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { PriceChart, type ChartSeries } from "@/components/PriceChart";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchSeriesObservations } from "@/lib/api";
import { DEFAULT_COMPARE_SERIES, KNOWN_BCB_SERIES } from "@/lib/bcb-series";
import { defaultHistoryRange } from "@/lib/dates";
import { useHistoryPages } from "@/lib/use-history-pages";

function parseSeriesParam(raw: string | null): string[] {
  const fallback = [...DEFAULT_COMPARE_SERIES];
  if (!raw) {
    return fallback;
  }
  const codes = raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return codes.length > 0 ? [...new Set(codes)].slice(0, 5) : fallback;
}

function ComparePageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const api = useApiStatus();
  const apiReady = api.status === "ok";
  const defaults = useMemo(() => defaultHistoryRange(5), []);
  const selected = parseSeriesParam(searchParams.get("series"));
  const [start, setStart] = useState(searchParams.get("start") ?? defaults.start);
  const [end, setEnd] = useState(searchParams.get("end") ?? defaults.end);
  const [applied, setApplied] = useState({
    start: searchParams.get("start") ?? defaults.start,
    end: searchParams.get("end") ?? defaults.end,
  });

  const paneA = useHistoryPages({
    key: JSON.stringify({ code: selected[0] ?? "", ...applied }),
    enabled: apiReady && Boolean(selected[0]),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        selected[0] ?? "",
        { start: applied.start || undefined, end: applied.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });
  const paneB = useHistoryPages({
    key: JSON.stringify({ code: selected[1] ?? "", ...applied }),
    enabled: apiReady && Boolean(selected[1]),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        selected[1] ?? "",
        { start: applied.start || undefined, end: applied.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });
  const paneC = useHistoryPages({
    key: JSON.stringify({ code: selected[2] ?? "", ...applied }),
    enabled: apiReady && Boolean(selected[2]),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        selected[2] ?? "",
        { start: applied.start || undefined, end: applied.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });
  const paneD = useHistoryPages({
    key: JSON.stringify({ code: selected[3] ?? "", ...applied }),
    enabled: apiReady && Boolean(selected[3]),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        selected[3] ?? "",
        { start: applied.start || undefined, end: applied.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });
  const paneE = useHistoryPages({
    key: JSON.stringify({ code: selected[4] ?? "", ...applied }),
    enabled: apiReady && Boolean(selected[4]),
    fetchPage: (cursor, signal) =>
      fetchSeriesObservations(
        selected[4] ?? "",
        { start: applied.start || undefined, end: applied.end || undefined, cursor },
        signal,
      ),
    itemsOf: (page) => page.observations,
    cursorOf: (page) => page.next_cursor,
  });

  const panes = [
    selected[0] ? { code: selected[0], history: paneA } : null,
    selected[1] ? { code: selected[1], history: paneB } : null,
    selected[2] ? { code: selected[2], history: paneC } : null,
    selected[3] ? { code: selected[3], history: paneD } : null,
    selected[4] ? { code: selected[4], history: paneE } : null,
  ].filter((item): item is { code: string; history: typeof paneA } => item !== null);

  function replaceSeries(next: string[]) {
    const qs = new URLSearchParams();
    qs.set("series", next.join(","));
    if (applied.start) qs.set("start", applied.start);
    if (applied.end) qs.set("end", applied.end);
    router.replace(`/compare?${qs.toString()}`);
  }

  function applyFilters(range?: DateRangeValue) {
    const next = { start: range?.start ?? start, end: range?.end ?? end };
    setStart(next.start);
    setEnd(next.end);
    setApplied(next);
    const qs = new URLSearchParams();
    qs.set("series", selected.join(","));
    if (next.start) qs.set("start", next.start);
    if (next.end) qs.set("end", next.end);
    router.replace(`/compare?${qs.toString()}`);
  }

  function toggle(code: string) {
    const next = selected.includes(code)
      ? selected.filter((item) => item !== code)
      : [...selected, code].slice(0, 5);
    if (next.length === 0) {
      return;
    }
    replaceSeries(next);
  }

  const groups = new Map<string, ChartSeries[]>();
  for (const pane of panes) {
    if (pane.history.items.length === 0) {
      continue;
    }
    const unit = pane.history.firstPage?.unit ?? pane.history.items[0]?.unit ?? "unknown";
    const current = groups.get(unit) ?? [];
    current.push({
      key: pane.code,
      label: pane.code,
      rows: pane.history.items.map((row) => ({ date: row.date, raw: row.value })),
    });
    groups.set(unit, current);
  }

  const anyError = panes.find((pane) => pane.history.status === "error");
  const loading = panes.some((pane) => pane.history.status === "loading");
  const hasMore = panes.some((pane) => pane.history.hasMore);
  const loadingMore = panes.some((pane) => pane.history.loadingMore);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Comparar séries</h1>
        <p className="mt-1 text-sm text-slate-600">
          Sobreposição com N chamadas a{" "}
          <code className="font-mono text-xs">GET /v1/series/{"{code}"}/observations</code>. Séries
          com unidades diferentes (percent_per_day, percent_per_year, PTAX) ficam em gráficos
          separados.
        </p>
      </header>

      <fieldset className="rounded-lg border border-slate-200 bg-white p-4">
        <legend className="text-sm font-medium text-slate-800">Séries BCB</legend>
        <div className="mt-2 flex flex-col gap-2">
          {KNOWN_BCB_SERIES.map((item) => (
            <label key={item.code} className="flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={selected.includes(item.code)}
                disabled={!apiReady}
                onChange={() => toggle(item.code)}
              />
              <span>
                {item.name}{" "}
                <span className="font-mono text-xs text-teal-800">{item.code}</span>{" "}
                <span className="text-xs text-slate-500">({item.unit})</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <DateRangeForm
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onSubmit={applyFilters}
        disabled={!apiReady}
      />

      {api.status !== "unreachable" && loading ? <LoadingState label="Carregando séries…" /> : null}
      {panes.map((pane) =>
        pane.history.status === "error" ? (
          <ErrorBanner key={pane.code} error={pane.history.error} label={pane.code} />
        ) : null,
      )}

      {apiReady && groups.size > 0
        ? [...groups.entries()].map(([unit, series]) => (
            <section key={unit} className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-slate-900">
                Unidade <span className="font-mono">{unit}</span>
              </h2>
              <PriceChart series={series} />
            </section>
          ))
        : null}

      {apiReady && !loading && groups.size === 0 && !anyError ? (
        <EmptyState>
          <p>Nenhuma observação carregada para as séries selecionadas.</p>
        </EmptyState>
      ) : null}

      <LoadMoreButton
        hasMore={hasMore}
        loading={loadingMore}
        onClick={() => {
          for (const pane of panes) {
            pane.history.loadMore();
          }
        }}
      />
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8">
          <LoadingState label="Carregando comparação…" />
        </div>
      }
    >
      <ComparePageInner />
    </Suspense>
  );
}
