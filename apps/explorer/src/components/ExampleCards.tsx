"use client";

import Link from "next/link";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { OfflineState } from "@/components/OfflineState";
import { SkeletonBlock } from "@/components/Status";
import {
  fetchFundLatest,
  fetchQuoteLatest,
  fetchSeriesLatest,
  formatApiError,
  isNotFoundError,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import {
  BRAZIL_HOME_EXAMPLES,
  HOME_EXAMPLES,
  SECONDARY_HOME_EXAMPLES,
  type HomeExample,
} from "@/lib/examples";
import { useClientFetch } from "@/lib/use-client-fetch";

export { HOME_EXAMPLES };

type LatestValue = {
  date: string;
  value: string;
  extra: string;
};

async function loadLatest(example: HomeExample): Promise<LatestValue> {
  if (example.kind === "series") {
    const row = await fetchSeriesLatest(example.identifier);
    return {
      date: row.date,
      value: row.value,
      extra: `${row.unit} · ${row.source}`,
    };
  }
  if (example.kind === "fund") {
    const row = await fetchFundLatest(example.identifier);
    return {
      date: row.date,
      value: row.price,
      extra: `${row.price_type} · ${row.source}`,
    };
  }
  const row = await fetchQuoteLatest(example.identifier);
  return {
    date: row.date,
    value: row.price,
    extra: `${row.price_type} · ${row.source}`,
  };
}

function ExampleCard({ example }: { example: HomeExample }) {
  const api = useApiStatus();
  const state = useClientFetch(`${example.kind}:${example.identifier}`, () => loadLatest(example), {
    enabled: api.status === "ok",
  });
  const notFound = state.status === "error" && isNotFoundError(state.error);

  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">{example.title}</h3>
      <p className="mt-1 font-mono text-sm text-teal-800">{example.identifier}</p>
      <p className="mt-2 text-sm text-slate-600">{example.description}</p>
      <div className="mt-3 min-h-[4.5rem]">
        {api.status === "unreachable" ? <OfflineState compact /> : null}
        {api.status !== "unreachable" && (api.status === "loading" || state.status === "loading") ? (
          <SkeletonBlock label="Carregando último valor…" />
        ) : null}
        {state.status === "success" ? (
          <p>
            <span className="block font-mono text-lg tabular-nums text-slate-900">
              {state.data.value}
            </span>
            <span className="text-xs text-slate-500">
              {state.data.date} · {state.data.extra}
            </span>
          </p>
        ) : null}
        {state.status === "error" ? (
          <p
            role="alert"
            className="break-words font-mono text-xs text-red-800"
            title={formatApiError(state.error)}
          >
            {formatApiError(state.error)}
            {notFound ? ` — ${copy.common.noSynthetic}.` : null}
          </p>
        ) : null}
      </div>
      <Link
        href={example.href}
        className="mt-auto pt-3 text-sm font-medium text-teal-800 hover:underline"
      >
        {copy.common.openHistory}
      </Link>
    </article>
  );
}

export function ExampleCards() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {BRAZIL_HOME_EXAMPLES.map((example) => (
          <ExampleCard key={example.identifier} example={example} />
        ))}
      </div>
      {SECONDARY_HOME_EXAMPLES.length > 0 ? (
        <aside className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-slate-700">Yahoo (não oficial)</h3>
          <p className="text-xs text-slate-500">
            Fonte secundária, fora do primeiro conjunto de exemplos brasileiros. Sem download em
            lote.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {SECONDARY_HOME_EXAMPLES.map((example) => (
              <ExampleCard key={example.identifier} example={example} />
            ))}
          </div>
        </aside>
      ) : null}
    </div>
  );
}
