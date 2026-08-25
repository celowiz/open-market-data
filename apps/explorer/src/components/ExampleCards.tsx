"use client";

import Link from "next/link";

import { LoadingState } from "@/components/Status";
import {
  fetchFundLatest,
  fetchQuoteLatest,
  fetchSeriesLatest,
  formatApiError,
} from "@/lib/api";
import { useClientFetch } from "@/lib/use-client-fetch";

type ExampleKind = "quote" | "series" | "fund";

type Example = {
  kind: ExampleKind;
  title: string;
  identifier: string;
  href: string;
  description: string;
};

type LatestValue = {
  date: string;
  value: string;
  extra: string;
};

export const HOME_EXAMPLES: Example[] = [
  {
    kind: "quote",
    title: "Tesouro",
    identifier: "LTN:2029-01-01",
    href: `/quotes/${encodeURIComponent("LTN:2029-01-01")}`,
    description: "Government bond quote (title + maturity).",
  },
  {
    kind: "series",
    title: "BCB",
    identifier: "BCB:CDI_DAILY",
    href: `/series/${encodeURIComponent("BCB:CDI_DAILY")}`,
    description: "CDI daily market series observation.",
  },
  {
    kind: "fund",
    title: "CVM",
    identifier: "00017024000153",
    href: `/funds/${encodeURIComponent("00017024000153")}`,
    description: "Fund unit value by CNPJ.",
  },
  {
    kind: "quote",
    title: "B3 equity",
    identifier: "PETR4",
    href: `/quotes/${encodeURIComponent("PETR4")}`,
    description: "Exchange equity last/close quote.",
  },
  {
    kind: "quote",
    title: "B3 future",
    identifier: "DI1F27",
    href: `/quotes/${encodeURIComponent("DI1F27")}`,
    description: "DI future official settlement.",
  },
  {
    kind: "quote",
    title: "Yahoo",
    identifier: "AAPL",
    href: `/quotes/${encodeURIComponent("AAPL")}`,
    description: "Unofficial global equity close (local API).",
  },
];

async function loadLatest(example: Example): Promise<LatestValue> {
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

function ExampleCard({ example }: { example: Example }) {
  const state = useClientFetch(`${example.kind}:${example.identifier}`, () =>
    loadLatest(example),
  );
  const notFound =
    state.status === "error" &&
    (formatApiError(state.error).includes("404") ||
      formatApiError(state.error).toLowerCase().includes("not found"));

  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">{example.title}</h3>
      <p className="mt-1 font-mono text-sm text-teal-800">{example.identifier}</p>
      <p className="mt-2 text-sm text-slate-600">{example.description}</p>
      <div className="mt-3 min-h-[4.5rem]">
        {state.status === "loading" ? (
          <LoadingState label="Fetching latest from /v1…" />
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
            {notFound ? " — no synthetic price." : null}
          </p>
        ) : null}
      </div>
      <Link
        href={example.href}
        className="mt-auto pt-3 text-sm font-medium text-teal-800 hover:underline"
      >
        Open history
      </Link>
    </article>
  );
}

export function ExampleCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {HOME_EXAMPLES.map((example) => (
        <ExampleCard key={example.identifier} example={example} />
      ))}
    </div>
  );
}
