"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { useSearchQuery } from "@/components/SearchQueryProvider";
import { EmptyState, LoadingState } from "@/components/Status";
import { searchInstruments } from "@/lib/api";
import { kindForIdentifier } from "@/lib/asset";
import { copy, offlineSearchHint } from "@/lib/copy";
import { HOME_EXAMPLES } from "@/lib/examples";
import { guessOpenTarget, hrefForInstrument } from "@/lib/links";
import type { InstrumentSearchItem } from "@/lib/types";
import { fieldClass } from "@/lib/ui";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

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
  const pathname = usePathname();
  const router = useRouter();
  const { query, setQuery } = useSearchQuery();
  const localOrigin = useLocalPageOrigin();
  const inputId = useId();
  const headingId = useId();
  const compact = variant === "compact";
  const apiReady = api.status === "ok";
  const [payload, setPayload] = useState<SearchPayload>({
    q: "",
    instruments: null,
    error: null,
  });

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
  }, [apiReady, query]);

  const trimmed = query.trim();
  const guess = guessOpenTarget(query);
  const pending = Boolean(trimmed) && payload.q !== trimmed && apiReady;
  const results = payload.q === trimmed ? payload.instruments : null;
  const error = payload.q === trimmed ? payload.error : null;

  function selectInstrument(item: InstrumentSearchItem) {
    const identifier = item.identifiers[0] ?? item.instrument_id;
    const kind = kindForIdentifier(identifier, item.asset_class);
    if (pathname === "/") {
      const params = new URLSearchParams();
      params.set("id", identifier);
      params.set("kind", kind);
      router.replace(`/?${params.toString()}`, { scroll: false });
      setQuery("");
      return;
    }
    router.push(hrefForInstrument(item));
    setQuery("");
  }

  const resultsBlock = (
    <div className={compact ? "absolute z-20 mt-1 w-full" : "mt-4"}>
      {apiReady && !trimmed && !compact ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            Digite um identificador ou nome para buscar, ou abra o{" "}
            <Link href="/ativos" className="font-medium text-accent hover:underline">
              catálogo de ativos
            </Link>
            .
          </p>
          <div className="flex flex-wrap gap-2">
            {HOME_EXAMPLES.map((example) => (
              <Link
                key={example.identifier}
                href={example.href}
                className="rounded-full border border-border bg-elevated px-3 py-1 text-sm text-foreground hover:border-accent/40"
              >
                {example.title}
                <span className="ml-2 font-mono text-xs text-accent">{example.identifier}</span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
      {api.status === "unreachable" && !compact ? (
        <p className="text-sm text-muted">{offlineSearchHint(localOrigin)}</p>
      ) : null}
      {pending ? <LoadingState label="Buscando…" /> : null}
      {error ? <ErrorBanner error={error} /> : null}
      {results && results.length === 0 && !pending ? (
        <EmptyState>
          <p>Nenhum instrumento público corresponde a esta consulta.</p>
          <p className="mt-2 text-xs text-muted">{copy.common.historyLoading}</p>
          {guess ? (
            <p className="mt-2">
              Ainda assim abrir a página:{" "}
              <Link href={guess.href} className="font-medium text-accent hover:underline">
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
              ? "max-h-80 divide-y divide-border overflow-auto rounded-xl border border-border bg-surface shadow-lg"
              : "divide-y divide-border rounded-xl border border-border bg-surface"
          }
        >
          {results.map((item) => (
            <li key={item.instrument_id}>
              {pathname === "/" ? (
                <button
                  type="button"
                  onClick={() => selectInstrument(item)}
                  className="block w-full px-3 py-3 text-left hover:bg-elevated"
                >
                  <SearchHit item={item} />
                </button>
              ) : (
                <Link href={hrefForInstrument(item)} className="block px-3 py-3 hover:bg-elevated">
                  <SearchHit item={item} />
                </Link>
              )}
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
          {copy.common.searchAssets}
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
          className={`w-full ${fieldClass}`}
        />
        {trimmed ? resultsBlock : null}
      </div>
    );
  }

  return (
    <section aria-labelledby={headingId} className="rounded-2xl border border-border bg-surface p-4">
      <h2 id={headingId} className="text-lg font-semibold text-foreground">
        {copy.common.searchAssets}
      </h2>
      <p className="mt-1 text-sm text-muted">
        Busca por nome ou identificador. Para ver a lista completa, abra o{" "}
        <Link href="/ativos" className="font-medium text-accent hover:underline">
          catálogo de ativos
        </Link>
        .
      </p>
      <div className="mt-3 flex flex-col gap-1">
        <label htmlFor={inputId} className="text-sm font-medium text-foreground">
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
          className={fieldClass}
        />
      </div>
      {resultsBlock}
    </section>
  );
}

function SearchHit({ item }: { item: InstrumentSearchItem }) {
  return (
    <>
      <p className="font-medium text-foreground">{item.name}</p>
      <p className="text-xs text-muted">
        {item.asset_class}
        {item.identifiers.length > 0 ? ` · ${item.identifiers.slice(0, 6).join(", ")}` : ""}
      </p>
    </>
  );
}
