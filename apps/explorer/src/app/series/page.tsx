"use client";

import Link from "next/link";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { SkeletonBlock } from "@/components/Status";
import { fetchSeriesLatest, formatApiError, isNotFoundError } from "@/lib/api";
import { KNOWN_BCB_SERIES } from "@/lib/bcb-series";
import { copy } from "@/lib/copy";
import { formatDisplayValue } from "@/lib/format-display-value";
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
    <article className="flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-foreground">{name}</h2>
      <p className="mt-1 font-mono text-sm text-accent">{code}</p>
      <p className="mt-1 text-xs text-muted">
        SGS {sgs} · <span className="font-mono">{unit}</span>
      </p>
      <div className="mt-3 min-h-[4.5rem]">
        {api.status === "unreachable" ? (
          <p className="font-mono text-lg tabular-nums text-muted" aria-hidden="true">
            —
          </p>
        ) : null}
        {api.status !== "unreachable" && (api.status === "loading" || latest.status === "loading") ? (
          <SkeletonBlock label="Carregando último valor…" />
        ) : null}
        {latest.status === "success" ? (
          <p>
            <span className="block font-mono text-lg tabular-nums text-foreground">
              {formatDisplayValue(latest.data.value, { kind: "series", unit: latest.data.unit })}
            </span>
            <span className="text-xs text-muted">
              {latest.data.date} · {latest.data.unit} · {latest.data.source}
            </span>
          </p>
        ) : null}
        {latest.status === "error" ? (
          <p className="break-words font-mono text-xs text-danger">
            {formatApiError(latest.error)}
            {isNotFoundError(latest.error) ? ` — ${copy.common.noSynthetic}.` : null}
          </p>
        ) : null}
      </div>
      <Link
        href={`/series/${encodeURIComponent(code)}`}
        className="mt-auto pt-3 text-sm font-medium text-accent hover:underline"
      >
        {copy.common.openHistory}
      </Link>
    </article>
  );
}

export default function SeriesIndexPage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:py-8">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Séries BCB</h1>
        <p className="mt-1 text-sm text-muted">
          Não existe <code className="font-mono text-xs">GET /v1/series</code>. Este catálogo lista
          as cinco séries SGS documentadas. Também resolvem pelos ids 11, 12, 432, 1 e 10813.
        </p>
        <p className="mt-2 text-sm">
          <Link href="/compare?series=BCB:CDI_DAILY,BCB:SELIC_DAILY" className="font-medium text-accent hover:underline">
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
