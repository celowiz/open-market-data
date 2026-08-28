"use client";

import Link from "next/link";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { OfflineState } from "@/components/OfflineState";
import { SkeletonBlock } from "@/components/Status";
import { fetchSeriesLatest, formatApiError, isNotFoundError } from "@/lib/api";
import { KNOWN_BCB_SERIES } from "@/lib/bcb-series";
import { copy } from "@/lib/copy";
import { useClientFetch } from "@/lib/use-client-fetch";

function SeriesCatalogCard({
  code,
  name,
  unit,
  sgs,
}: {
  code: string;
  name: string;
  unit: string;
  sgs: string;
}) {
  const api = useApiStatus();
  const latest = useClientFetch(`series-latest:${code}`, () => fetchSeriesLatest(code), {
    enabled: api.status === "ok",
  });

  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{name}</h2>
      <p className="mt-1 font-mono text-sm text-teal-800">{code}</p>
      <p className="mt-1 text-xs text-slate-500">
        SGS {sgs} · <span className="font-mono">{unit}</span>
      </p>
      <div className="mt-3 min-h-[4.5rem]">
        {api.status === "unreachable" ? <OfflineState compact /> : null}
        {api.status !== "unreachable" && (api.status === "loading" || latest.status === "loading") ? (
          <SkeletonBlock label="Carregando último valor…" />
        ) : null}
        {latest.status === "success" ? (
          <p>
            <span className="block font-mono text-lg tabular-nums text-slate-900">
              {latest.data.value}
            </span>
            <span className="text-xs text-slate-500">
              {latest.data.date} · {latest.data.unit} · {latest.data.source}
            </span>
          </p>
        ) : null}
        {latest.status === "error" ? (
          <p role="alert" className="break-words font-mono text-xs text-red-800">
            {formatApiError(latest.error)}
            {isNotFoundError(latest.error) ? ` — ${copy.common.noSynthetic}.` : null}
          </p>
        ) : null}
      </div>
      <Link
        href={`/series/${encodeURIComponent(code)}`}
        className="mt-auto pt-3 text-sm font-medium text-teal-800 hover:underline"
      >
        {copy.common.openHistory}
      </Link>
    </article>
  );
}

export default function SeriesIndexPage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Séries BCB</h1>
        <p className="mt-1 text-sm text-slate-600">
          Não existe <code className="font-mono text-xs">GET /v1/series</code>. Este catálogo lista
          as cinco séries SGS documentadas. Também resolvem pelos ids 11, 12, 432, 1 e 10813.
        </p>
        <p className="mt-2 text-sm">
          <Link href="/compare?series=BCB:CDI_DAILY,BCB:SELIC_DAILY" className="font-medium text-teal-800 hover:underline">
            Comparar CDI e Selic over
          </Link>
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {KNOWN_BCB_SERIES.map((item) => (
          <SeriesCatalogCard
            key={item.code}
            code={item.code}
            name={item.name}
            unit={item.unit}
            sgs={item.sgs}
          />
        ))}
      </div>
    </div>
  );
}
