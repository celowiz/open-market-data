"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { useSearchQuery } from "@/components/SearchQueryProvider";
import { EmptyState, LoadingState } from "@/components/Status";
import { searchInstruments } from "@/lib/api";
import { kindForIdentifier } from "@/lib/asset";
import { copy } from "@/lib/copy";
import { BRAZIL_HOME_EXAMPLES } from "@/lib/examples";
import {
  comboboxOptions,
  moveActiveIndex,
  optionDomId,
  SEARCH_DEBOUNCE_MS,
  type SearchComboboxOption,
} from "@/lib/search-combobox";
import { guessOpenTarget, hrefForInstrument } from "@/lib/links";
import { formatQuoteSpan, hasQuoteSpan } from "@/lib/span";
import type { InstrumentSearchItem } from "@/lib/types";
import { cn, fieldClass } from "@/lib/ui";

type SearchPayload = {
  q: string;
  instruments: InstrumentSearchItem[] | null;
  error: unknown;
};

export function InstrumentSearch({
  variant = "page",
  query: queryProp,
  onQueryChange,
}: {
  variant?: "page" | "compact";
  query?: string;
  onQueryChange?: (value: string) => void;
}) {
  const api = useApiStatus();
  const pathname = usePathname();
  const router = useRouter();
  const ctx = useSearchQuery();
  const query = queryProp ?? ctx.query;
  const setQuery = onQueryChange ?? ctx.setQuery;
  const inputId = useId();
  const headingId = useId();
  const listboxId = useId();
  const compact = variant === "compact";
  const apiReady = api.status === "ok";
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(!compact);
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
    }, SEARCH_DEBOUNCE_MS);
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
  const options = useMemo(
    () => comboboxOptions({ query, instruments: results, shortcuts: BRAZIL_HOME_EXAMPLES }),
    [query, results],
  );
  const optionsKey = options.map((option) => option.id).join("|");
  const showPanel = compact ? open : true;
  const [activeIndex, setActiveIndex] = useState(0);
  const [indexedKey, setIndexedKey] = useState(optionsKey);
  if (optionsKey !== indexedKey) {
    setIndexedKey(optionsKey);
    setActiveIndex(options.length > 0 ? 0 : -1);
  }
  const activeOption = activeIndex >= 0 ? options[activeIndex] : undefined;
  const activeDescendant =
    showPanel && activeOption ? optionDomId(listboxId, activeIndex) : undefined;

  useEffect(() => {
    if (!compact || !open) {
      return;
    }
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [compact, open]);

  useEffect(() => {
    if (!showPanel || activeIndex < 0 || options.length === 0) {
      return;
    }
    if (!trimmed && !compact) {
      return;
    }
    document.getElementById(optionDomId(listboxId, activeIndex))?.scrollIntoView({
      block: "nearest",
    });
  }, [activeIndex, compact, listboxId, options.length, showPanel, trimmed]);

  function selectInstrument(item: InstrumentSearchItem) {
    const identifier = item.identifiers[0] ?? item.instrument_id;
    const kind = kindForIdentifier(identifier, item.asset_class);
    setOpen(false);
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

  function activateOption(option: SearchComboboxOption) {
    if (option.kind === "shortcut") {
      setOpen(false);
      setQuery("");
      router.push(option.example.href);
      return;
    }
    selectInstrument(option.item);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(options.length > 0 ? 0 : -1);
        return;
      }
      setActiveIndex((current) => moveActiveIndex(current, 1, options.length));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(options.length > 0 ? options.length - 1 : -1);
        return;
      }
      setActiveIndex((current) => moveActiveIndex(current, -1, options.length));
      return;
    }
    if (event.key === "Home" && options.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(0);
      return;
    }
    if (event.key === "End" && options.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(options.length - 1);
      return;
    }
    if (event.key === "Enter" && showPanel && activeOption) {
      event.preventDefault();
      activateOption(activeOption);
    }
  }

  const listbox =
    showPanel && options.length > 0 ? (
    <ul
      id={listboxId}
      role="listbox"
      aria-label={trimmed ? copy.common.searchAssets : copy.common.examples}
      className={
        trimmed
          ? compact
            ? "max-h-80 divide-y divide-border overflow-auto rounded-xl border border-border bg-surface shadow-lg"
            : "divide-y divide-border rounded-xl border border-border bg-surface"
          : cn(
              "flex flex-wrap gap-2",
              compact && "rounded-xl border border-border bg-surface p-2 shadow-lg",
            )
      }
    >
      {options.map((option, index) => {
        const selected = index === activeIndex;
        const optionId = optionDomId(listboxId, index);
        const rowClass = cn(
          trimmed
            ? "block w-full px-3 py-3 text-left hover:bg-elevated"
            : "inline-flex min-h-11 items-center rounded-full border border-border bg-elevated px-3 py-2 text-sm text-foreground hover:border-accent/40",
          selected && (trimmed ? "bg-elevated" : "border-accent/60"),
          trimmed && "min-h-11",
        );
        if (option.kind === "shortcut") {
          return (
            <li key={option.id} role="presentation">
              <Link
                id={optionId}
                role="option"
                aria-selected={selected}
                href={option.example.href}
                className={rowClass}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setOpen(false);
                  setQuery("");
                }}
              >
                {option.example.title}
                <span className="ml-2 font-mono text-xs text-accent">{option.example.identifier}</span>
              </Link>
            </li>
          );
        }
        return (
          <li key={option.id} role="presentation">
            {pathname === "/" ? (
              <button
                id={optionId}
                type="button"
                role="option"
                aria-selected={selected}
                className={rowClass}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectInstrument(option.item)}
              >
                <SearchHit item={option.item} />
              </button>
            ) : (
              <Link
                id={optionId}
                role="option"
                aria-selected={selected}
                href={hrefForInstrument(option.item)}
                className={rowClass}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setOpen(false);
                  setQuery("");
                }}
              >
                <SearchHit item={option.item} />
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  ) : null;

  const resultsBlock = showPanel ? (
    <div className={compact ? "absolute z-40 mt-1 w-full" : "mt-4"}>
      {!trimmed ? (
        <p className={cn("mb-2 text-muted", compact ? "text-xs" : "text-sm")}>
          {copy.common.curatedEmptySearch}
        </p>
      ) : null}
      {pending ? <LoadingState label="Buscando…" /> : null}
      {error && api.status !== "unreachable" ? <ErrorBanner error={error} /> : null}
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
      {listbox}
    </div>
  ) : null;

  const input = (
    <input
      id={inputId}
      name="q"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={showPanel}
      aria-controls={options.length > 0 ? listboxId : undefined}
      aria-activedescendant={activeDescendant}
      aria-busy={pending || undefined}
      autoComplete="off"
      autoCorrect="off"
      spellCheck={false}
      inputMode="search"
      placeholder="PETR4, LTN:2029-01-01, CNPJ…"
      value={query}
      onChange={(event) => {
        setQuery(event.target.value);
        setOpen(true);
      }}
      onFocus={() => setOpen(true)}
      onKeyDown={onKeyDown}
      className={cn("w-full min-w-0 min-h-11", fieldClass)}
    />
  );

  if (compact) {
    return (
      <div ref={rootRef} className="relative min-w-0">
        <label htmlFor={inputId} className="sr-only">
          {copy.common.searchAssets}
        </label>
        {input}
        {resultsBlock}
      </div>
    );
  }

  return (
    <section aria-labelledby={headingId} className="rounded-2xl border border-border bg-surface p-4">
      <h2 id={headingId} className="text-lg font-semibold text-foreground">
        {copy.common.searchAssets}
      </h2>
      <p className="mt-1 text-sm text-muted">
        Busca por nome ou identificador. Sem consulta, atalhos — a API exige q=.
      </p>
      <div ref={rootRef} className="relative mt-3 flex flex-col gap-1">
        <label htmlFor={inputId} className="text-sm font-medium text-foreground">
          Consulta
        </label>
        {input}
        {resultsBlock}
      </div>
    </section>
  );
}

function SearchHit({ item }: { item: InstrumentSearchItem }) {
  const spanLabel = hasQuoteSpan(item) ? formatQuoteSpan(item) : null;
  return (
    <>
      <p className="font-medium text-foreground">{item.name}</p>
      <p className="text-xs text-muted">
        {item.asset_class}
        {item.identifiers.length > 0 ? ` · ${item.identifiers.slice(0, 6).join(", ")}` : ""}
      </p>
      {spanLabel ? <p className="mt-1 font-mono text-[11px] text-muted">{spanLabel}</p> : null}
    </>
  );
}
