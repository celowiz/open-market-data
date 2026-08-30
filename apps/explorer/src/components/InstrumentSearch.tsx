"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { copy } from "@/lib/copy";
import { HOME_EXAMPLES } from "@/lib/examples";
import { EmptyState, LoadingState } from "@/components/Status";
import { searchInstruments } from "@/lib/api";
import { guessOpenTarget, hrefForInstrument } from "@/lib/links";
import type { InstrumentSearchItem } from "@/lib/types";

type SearchPayload = {
  q: string;
  instruments: InstrumentSearchItem[] | null;
  error: unknown;
};

export function InstrumentSearch({
  variant = "page",
}: {
  variant?: "page" | "compact";
}) {
  const api = useApiStatus();
  const inputId = useId();
  const headingId = useId();
  const [query, setQuery] = useState("");
  const [payload, setPayload] = useState<SearchPayload>({
    q: "",
    instruments: null,
    error: null,
  });
  const compact = variant === "compact";
  const apiReady = api.status === "ok";

  useEffect(() => {
    const q = query.trim();
    if (!q || !apiReady) {
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
  }, [query, apiReady]);

  const trimmed = query.trim();
  const guess = guessOpenTarget(query);
  const pending = Boolean(trimmed) && payload.q !== trimmed && apiReady;
  const results = payload.q === trimmed ? payload.instruments : null;
  const error = payload.q === trimmed ? payload.error : null;

  const resultsBlock = (
    <div className={compact ? "absolute z-20 mt-1 w-full" : "mt-4"}>
      {apiReady && !trimmed && !compact ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-slate-600">
            Digite um identificador ou nome para buscar, ou abra o{" "}
            <Link href="/instruments" className="font-medium text-teal-800 hover:underline">
              catálogo de ativos
            </Link>
            .
          </p>
          <div className="flex flex-wrap gap-2">
            {HOME_EXAMPLES.map((example) => (
              <Link
                key={example.identifier}
                href={example.href}
                className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-sm text-slate-800 hover:bg-white"
              >
                {example.title}
                <span className="ml-2 font-mono text-xs text-teal-800">{example.identifier}</span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
      {pending ? <LoadingState label="Buscando…" /> : null}
      {error ? <ErrorBanner error={error} /> : null}
      {results && results.length === 0 && !pending ? (
        <EmptyState>
          <p>Nenhum instrumento público corresponde a esta consulta.</p>
          <p className="mt-2 text-xs text-slate-500">{copy.common.backfillSecondary}</p>
          {guess ? (
            <p className="mt-2">
              Ainda assim abrir a página:{" "}
              <Link href={guess.href} className="font-medium text-teal-800 hover:underline">
                {guess.label}
              </Link>
            </p>
          ) : null}
        </EmptyState>
      ) : null}
      {results && results.length > 0 ? (
        <ul
          className={
            compact
              ? "max-h-80 divide-y divide-slate-100 overflow-auto rounded-md border border-slate-200 bg-white shadow-sm"
              : "divide-y divide-slate-100 rounded-md border border-slate-200 bg-white"
          }
        >
          {results.map((item) => (
            <li key={item.instrument_id}>
              <Link href={hrefForInstrument(item)} className="block px-3 py-3 hover:bg-slate-50">
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
  );

  if (compact) {
    return (
      <div className="relative">
        <label htmlFor={inputId} className="sr-only">
          Buscar instrumentos
        </label>
        <input
          id={inputId}
          name="q"
          type="search"
          autoComplete="off"
          placeholder="PETR4, LTN:2029-01-01, CNPJ…"
          value={query}
          disabled={!apiReady && api.status === "unreachable"}
          onChange={(event) => setQuery(event.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
        />
        {trimmed ? resultsBlock : null}
      </div>
    );
  }

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <h2 id={headingId} className="text-lg font-semibold text-slate-900">
        Buscar instrumentos
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Consulta <code className="font-mono text-xs">GET /v1/instruments</code>. Digite para buscar
        por nome ou identificador. Para ver a lista completa, abra o{" "}
        <Link href="/instruments" className="font-medium text-teal-800 hover:underline">
          catálogo de ativos
        </Link>
        .
      </p>
      <div className="mt-3 flex flex-col gap-1">
        <label htmlFor={inputId} className="text-sm font-medium text-slate-800">
          Consulta
        </label>
        <input
          id={inputId}
          name="q"
          type="search"
          autoComplete="off"
          placeholder="PETR4, LTN:2029-01-01, CNPJ de fundo…"
          value={query}
          disabled={!apiReady && api.status === "unreachable"}
          onChange={(event) => setQuery(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
        />
      </div>
      {resultsBlock}
    </section>
  );
}
