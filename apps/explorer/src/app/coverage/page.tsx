"use client";

import Link from "next/link";
import { useState } from "react";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { CoverageChart } from "@/components/CoverageChart";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { EmptyState, LoadingState } from "@/components/Status";
import { COVERAGE_PAGE_SIZE, fetchCoverage } from "@/lib/api";
import { offlineFormHint } from "@/lib/copy";
import { todayIso } from "@/lib/dates";
import { formatDisplayValue } from "@/lib/format-display-value";
import { hrefForIdentifier } from "@/lib/links";
import type { CoverageUniverse } from "@/lib/types";
import { useHistoryPages } from "@/lib/use-history-pages";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

const COVERAGE_UNIVERSES: CoverageUniverse[] = ["scratch", "example", "operator"];

function isCoverageUniverse(value: string): value is CoverageUniverse {
  return COVERAGE_UNIVERSES.includes(value as CoverageUniverse);
}

export default function CoveragePage() {
  const api = useApiStatus();
  const localOrigin = useLocalPageOrigin();
  const apiReady = api.status === "ok";
  const [dateInput, setDateInput] = useState(todayIso());
  const [universe, setUniverse] = useState<CoverageUniverse>("scratch");
  const [applied, setApplied] = useState<{ date: string; universe: CoverageUniverse }>({
    date: todayIso(),
    universe: "scratch",
  });

  const history = useHistoryPages({
    key: JSON.stringify(applied),
    enabled: apiReady,
    fetchPage: (cursor, signal) =>
      fetchCoverage(
        {
          date: applied.date,
          universe: applied.universe,
          limit: COVERAGE_PAGE_SIZE,
          cursor: cursor ? Number(cursor) : 0,
        },
        signal,
      ),
    itemsOf: (page) => page.results,
    cursorOf: (page) => (page.next_cursor === null || page.next_cursor === undefined ? null : String(page.next_cursor)),
  });

  const data = history.firstPage;
  const rows = history.items;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Cobertura</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/coverage?date=</code> para o universo
          escolhido (padrão: scratch, IBOV/SMLL/futuros). Preços ausentes permanecem em branco.
        </p>
      </header>

      <form
        className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (apiReady) {
            setApplied({ date: dateInput, universe });
          }
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="coverage-date" className="text-sm font-medium text-slate-800">
            Data de referência
          </label>
          <input
            id="coverage-date"
            name="date"
            type="date"
            required
            value={dateInput}
            disabled={!apiReady}
            onChange={(event) => setDateInput(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="coverage-universe" className="text-sm font-medium text-slate-800">
            Universo
          </label>
          <select
            id="coverage-universe"
            name="universe"
            value={universe}
            disabled={!apiReady}
            onChange={(event) => {
              const next = event.target.value;
              if (isCoverageUniverse(next)) {
                setUniverse(next);
              }
            }}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          >
            <option value="scratch">scratch</option>
            <option value="example">example</option>
            <option value="operator">operator</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={!apiReady}
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          Carregar cobertura
        </button>
      </form>
      {!apiReady && api.status === "unreachable" ? (
        <p className="text-sm text-slate-600">{offlineFormHint(localOrigin)}</p>
      ) : null}

      {api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando cobertura…" />
      ) : null}
      {history.status === "error" ? <ErrorBanner error={history.error} /> : null}

      {data && (history.status === "success" || rows.length > 0) ? (
        <>
          <section className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">Data</p>
              <p className="font-mono">{data.date}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Universo</p>
              <p>
                {data.universe} ({data.mode})
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Com preço</p>
              <p>
                {data.priced} / {data.universe_size} ({data.priced_pct})
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Motivos de ausência</p>
              <p>
                {Object.keys(data.missing_reason_counts).length === 0
                  ? "—"
                  : Object.entries(data.missing_reason_counts)
                      .map(([reason, count]) => `${reason}: ${count}`)
                      .join(", ")}
              </p>
            </div>
          </section>

          <CoverageChart data={data} rows={rows} />

          {rows.length === 0 ? (
            <EmptyState>
              <p>A cobertura não devolveu linhas para esta data.</p>
            </EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="min-w-full text-left text-sm">
                <caption className="sr-only">Resultados de cobertura</caption>
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Instrumento
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Classe
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Provedor
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Data de referência
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Preço
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Tipo de preço
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Defasagem
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Motivo da ausência
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr
                      key={`${row.instrument}-${row.reference_date}-${index}`}
                      className="border-t border-slate-100"
                    >
                      <td className="px-3 py-2 font-mono">
                        <Link
                          href={hrefForIdentifier(row.instrument, row.asset_class)}
                          className="text-teal-800 hover:underline"
                        >
                          {row.instrument}
                        </Link>
                      </td>
                      <td className="px-3 py-2">{row.asset_class}</td>
                      <td className="px-3 py-2">{row.provider ?? "—"}</td>
                      <td className="px-3 py-2 font-mono">{row.reference_date}</td>
                      <td className="px-3 py-2 font-mono tabular-nums">
                        {row.price === null || row.price === undefined
                          ? "—"
                          : formatDisplayValue(row.price, { priceType: row.price_type })}
                      </td>
                      <td className="px-3 py-2 font-mono">{row.price_type ?? "—"}</td>
                      <td className="px-3 py-2">{row.status}</td>
                      <td className="px-3 py-2">{row.staleness ?? "—"}</td>
                      <td className="px-3 py-2">{row.missing_reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <LoadMoreButton
            hasMore={history.hasMore}
            loading={history.loadingMore}
            onClick={history.loadMore}
          />
        </>
      ) : null}
    </div>
  );
}
