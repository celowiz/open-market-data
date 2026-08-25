"use client";

import { useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState, LoadingState } from "@/components/Status";
import { fetchCoverage } from "@/lib/api";
import { todayIso } from "@/lib/dates";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function CoveragePage() {
  const [dateInput, setDateInput] = useState(todayIso());
  const [appliedDate, setAppliedDate] = useState(todayIso());
  const state = useClientFetch(`coverage:${appliedDate}`, () => fetchCoverage(appliedDate));

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Coverage</h1>
        <p className="mt-1 text-sm text-slate-600">
          <code className="font-mono text-xs">GET /v1/coverage?date=</code> for the example
          universe. Missing prices stay blank.
        </p>
      </header>

      <form
        className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          setAppliedDate(dateInput);
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="coverage-date" className="text-sm font-medium text-slate-800">
            Reference date
          </label>
          <input
            id="coverage-date"
            name="date"
            type="date"
            required
            value={dateInput}
            onChange={(event) => setDateInput(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
        >
          Load coverage
        </button>
      </form>

      {state.status === "loading" ? <LoadingState label="Loading coverage…" /> : null}
      {state.status === "error" ? <ErrorBanner error={state.error} /> : null}

      {state.status === "success" ? (
        <>
          <section className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">Date</p>
              <p className="font-mono">{state.data.date}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Universe</p>
              <p>
                {state.data.universe} ({state.data.mode})
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Priced</p>
              <p>
                {state.data.priced} / {state.data.universe_size} ({state.data.priced_pct})
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Missing reasons</p>
              <p>
                {Object.keys(state.data.missing_reason_counts).length === 0
                  ? "—"
                  : Object.entries(state.data.missing_reason_counts)
                      .map(([reason, count]) => `${reason}: ${count}`)
                      .join(", ")}
              </p>
            </div>
          </section>

          {state.data.results.length === 0 ? (
            <EmptyState>
              <p>Coverage returned no rows for this date.</p>
            </EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="min-w-full text-left text-sm">
                <caption className="sr-only">Coverage results</caption>
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Instrument
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Asset class
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Provider
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Reference date
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Price
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Price type
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Staleness
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Missing reason
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.results.map((row, index) => (
                    <tr
                      key={`${row.instrument}-${row.reference_date}-${index}`}
                      className="border-t border-slate-100"
                    >
                      <td className="px-3 py-2 font-mono">{row.instrument}</td>
                      <td className="px-3 py-2">{row.asset_class}</td>
                      <td className="px-3 py-2">{row.provider ?? "—"}</td>
                      <td className="px-3 py-2 font-mono">{row.reference_date}</td>
                      <td className="px-3 py-2 font-mono tabular-nums">
                        {row.price === null || row.price === undefined ? "—" : row.price}
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
          {state.data.next_cursor !== null && state.data.next_cursor !== undefined ? (
            <p className="text-sm text-slate-600">
              Additional rows exist (cursor {state.data.next_cursor}).
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
