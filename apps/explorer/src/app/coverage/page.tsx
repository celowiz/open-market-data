"use client";

import Link from "next/link";
import { useState } from "react";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { CoverageChart } from "@/components/CoverageChart";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadMoreButton } from "@/components/LoadMoreButton";
import { EmptyState, LoadingState } from "@/components/Status";
import { COVERAGE_PAGE_SIZE, fetchCoverage, fetchCoverageSpan, isNotFoundError, isTimeoutError } from "@/lib/api";
import { copy, offlineFormHint } from "@/lib/copy";
import { todayIso } from "@/lib/dates";
import { formatDisplayValue } from "@/lib/format-display-value";
import { hrefForIdentifier } from "@/lib/links";
import { formatPregoes } from "@/lib/span";
import type { CoverageSpanResponse, CoverageUniverse } from "@/lib/types";
import { useClientFetch } from "@/lib/use-client-fetch";
import { useHistoryPages } from "@/lib/use-history-pages";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

const COVERAGE_UNIVERSES: CoverageUniverse[] = ["scratch", "example", "operator"];

function isCoverageUniverse(value: string): value is CoverageUniverse {
  return COVERAGE_UNIVERSES.includes(value as CoverageUniverse);
}

function CoverageSpanSummary({ data }: { data: CoverageSpanResponse }) {
  return (
    <section className="grid gap-3 rounded-2xl border border-border bg-elevated p-4 text-sm sm:grid-cols-2 lg:grid-cols-5">
      <div>
        <p className="text-xs text-muted">Universo</p>
        <p>{data.universe}</p>
      </div>
      <div>
        <p className="text-xs text-muted">Com histórico</p>
        <p>
          {data.instruments_with_quotes} / {data.universe_size}
        </p>
      </div>
      <div>
        <p className="text-xs text-muted">{copy.common.firstQuote}</p>
        <p className="font-mono">{data.min_date ?? "—"}</p>
      </div>
      <div>
        <p className="text-xs text-muted">{copy.common.lastQuote}</p>
        <p className="font-mono">{data.max_date ?? "—"}</p>
      </div>
      <div>
        <p className="text-xs text-muted">{copy.common.sessions}</p>
        <p className="font-mono tabular-nums">{formatPregoes(data.quote_count)}</p>
      </div>
    </section>
  );
}

export default function CoveragePage() {
  const api = useApiStatus();
  const localOrigin = useLocalPageOrigin();
  const apiReady = api.status === "ok";
  const [dateInput, setDateInput] = useState(todayIso());
  const [universe, setUniverse] = useState<CoverageUniverse>("scratch");
  const [applied, setApplied] = useState<{ date: string; universe: CoverageUniverse } | null>(null);

  const span = useClientFetch(
    `coverage-span:${universe}`,
    () => fetchCoverageSpan({ universe }),
    { enabled: apiReady },
  );

  const history = useHistoryPages({
    key: JSON.stringify(applied),
    enabled: apiReady && applied !== null,
    fetchPage: (cursor, signal) =>
      fetchCoverage(
        {
          date: applied?.date ?? dateInput,
          universe: applied?.universe ?? universe,
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
  const dateCoveragePending = applied === null;
  const dateCoverageUnavailable =
    history.status === "error" && (isNotFoundError(history.error) || isTimeoutError(history.error));

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:py-8">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Cobertura</h1>
        <p className="mt-1 text-sm text-muted">
          Resumo rápido de <code className="font-mono text-xs">GET /v1/coverage/span</code> (primeira e
          última data no banco). O motor completo por data{" "}
          <code className="font-mono text-xs">GET /v1/coverage?date=</code> continua disponível abaixo e
          não é carregado automaticamente.
        </p>
      </header>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1">
          <label htmlFor="coverage-universe" className="text-sm font-medium text-foreground">
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
            className="rounded-xl border border-border px-3 py-2 text-sm disabled:bg-elevated"
          >
            <option value="scratch">scratch</option>
            <option value="example">example</option>
            <option value="operator">operator</option>
          </select>
        </div>
      </div>
      {!apiReady && api.status === "unreachable" ? (
        <p className="text-sm text-muted">{offlineFormHint(localOrigin)}</p>
      ) : null}

      {api.status !== "unreachable" && span.status === "loading" ? (
        <LoadingState label="Carregando intervalo de cotações…" />
      ) : null}
      {span.status === "error" ? (
        isNotFoundError(span.error) || isTimeoutError(span.error) ? (
          <EmptyState>
            <p>O intervalo deste universo ainda não está disponível.</p>
            <p className="mt-2 text-xs text-muted">{copy.common.historyLoading}</p>
          </EmptyState>
        ) : (
          <ErrorBanner error={span.error} />
        )
      ) : null}
      {span.status === "success" && span.data.instruments_with_quotes === 0 ? (
        <>
          <CoverageSpanSummary data={span.data} />
          <EmptyState>
            <p>Nenhuma cotação deste universo chegou ainda.</p>
            <p className="mt-2 text-xs text-muted">{copy.common.historyLoading}</p>
          </EmptyState>
        </>
      ) : null}
      {span.status === "success" && span.data.instruments_with_quotes > 0 ? (
        <CoverageSpanSummary data={span.data} />
      ) : null}

      <form
        className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (apiReady) {
            setApplied({ date: dateInput, universe });
          }
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="coverage-date" className="text-sm font-medium text-foreground">
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
            className="rounded-xl border border-border px-3 py-2 text-sm disabled:bg-elevated"
          />
        </div>
        <button
          type="submit"
          disabled={!apiReady}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:brightness-110 disabled:cursor-not-allowed disabled:bg-elevated"
        >
          Carregar cobertura do dia
        </button>
      </form>
      <p className="text-xs text-muted">
        Esta consulta por data usa o motor completo e pode ser lenta enquanto a ingestão está
        gravando. O resumo acima não depende dela.
      </p>

      {dateCoveragePending ? null : api.status !== "unreachable" && history.status === "loading" ? (
        <LoadingState label="Carregando cobertura…" />
      ) : null}
      {dateCoveragePending ? null : history.status === "error" && dateCoverageUnavailable ? (
        <EmptyState>
          <p>A cobertura desta data ainda não está disponível ou a consulta excedeu o tempo.</p>
          <p className="mt-2 text-xs text-muted">{copy.common.historyLoading}</p>
        </EmptyState>
      ) : null}
      {dateCoveragePending ? null : history.status === "error" && !dateCoverageUnavailable ? (
        <ErrorBanner error={history.error} />
      ) : null}

      {data && (history.status === "success" || rows.length > 0) ? (
        <>
          <section className="grid gap-3 rounded-2xl border border-border bg-elevated p-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs text-muted">Data</p>
              <p className="font-mono">{data.date}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Universo</p>
              <p>
                {data.universe} ({data.mode})
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Com preço</p>
              <p>
                {data.priced} / {data.universe_size} ({data.priced_pct})
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Motivos de ausência</p>
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
              <p className="mt-2 text-xs text-muted">{copy.common.historyLoading}</p>
            </EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
              <table className="min-w-full text-left text-sm">
                <caption className="sr-only">Resultados de cobertura</caption>
                <thead className="bg-elevated text-xs uppercase tracking-wide text-muted">
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
                      className="border-t border-border/80"
                    >
                      <td className="px-3 py-2 font-mono">
                        <Link
                          href={hrefForIdentifier(row.instrument, row.asset_class)}
                          className="text-accent hover:underline"
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
