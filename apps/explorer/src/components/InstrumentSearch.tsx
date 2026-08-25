"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState, LoadingState } from "@/components/Status";
import { searchInstruments } from "@/lib/api";
import { guessOpenTarget, hrefForInstrument } from "@/lib/links";
import type { InstrumentSearchItem } from "@/lib/types";

type SearchPayload = {
  q: string;
  instruments: InstrumentSearchItem[] | null;
  error: unknown;
};

export function InstrumentSearch() {
  const [query, setQuery] = useState("");
  const [payload, setPayload] = useState<SearchPayload>({
    q: "",
    instruments: null,
    error: null,
  });

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchInstruments(q, 20, controller.signal).then(
        (data) => {
          setPayload({ q, instruments: data.instruments, error: null });
        },
        (err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          setPayload({ q, instruments: null, error: err });
        },
      );
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const trimmed = query.trim();
  const guess = guessOpenTarget(query);
  const pending = Boolean(trimmed) && payload.q !== trimmed;
  const results = payload.q === trimmed ? payload.instruments : null;
  const error = payload.q === trimmed ? payload.error : null;

  return (
    <section aria-labelledby="search-heading" className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 id="search-heading" className="text-lg font-semibold text-slate-900">
        Search instruments
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Queries <code className="font-mono text-xs">GET /v1/instruments?q=</code>. Empty search is
        not sent (the API returns 400).
      </p>
      <div className="mt-3 flex flex-col gap-1">
        <label htmlFor="instrument-q" className="text-sm font-medium text-slate-800">
          Search query
        </label>
        <input
          id="instrument-q"
          name="q"
          type="search"
          autoComplete="off"
          placeholder="PETR4, LTN:2029-01-01, fund CNPJ…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>
      <div className="mt-4">
        {!trimmed ? (
          <p className="text-sm text-slate-600">Type an identifier or name to search.</p>
        ) : null}
        {pending ? <LoadingState label="Searching…" /> : null}
        {error ? <ErrorBanner error={error} /> : null}
        {results && results.length === 0 && !pending ? (
          <EmptyState>
            <p>No public instruments matched this query.</p>
            <p className="mt-2">
              If the database is empty, run a historical backfill (
              <code className="font-mono text-xs">marketdata backfill</code>) and keep FastAPI
              running on port 8000.
            </p>
            {guess ? (
              <p className="mt-2">
                Still try the chart page:{" "}
                <Link href={guess.href} className="font-medium text-teal-800 hover:underline">
                  {guess.label}
                </Link>
              </p>
            ) : null}
          </EmptyState>
        ) : null}
        {results && results.length > 0 ? (
          <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
            {results.map((item) => (
              <li key={item.instrument_id}>
                <Link
                  href={hrefForInstrument(item)}
                  className="block px-3 py-3 hover:bg-slate-50"
                >
                  <p className="font-medium text-slate-900">{item.name}</p>
                  <p className="text-xs text-slate-500">
                    {item.asset_class}
                    {item.identifiers.length > 0
                      ? ` · ${item.identifiers.slice(0, 6).join(", ")}`
                      : ""}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
