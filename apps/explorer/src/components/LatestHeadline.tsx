"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import {
  fetchFundLatest,
  fetchQuoteLatest,
  fetchSeriesLatest,
  formatApiError,
  isNotFoundError,
  lookupInstrumentName,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatDisplayValue } from "@/lib/format-display-value";
import { useClientFetch } from "@/lib/use-client-fetch";

type HeadlineValue = {
  date: string;
  value: string;
  extra: string;
  priceType?: string;
  unit?: string | null;
  kind: "quote" | "series";
};

export function LatestHeadline({
  kind,
  identifier,
  priceType,
}: {
  kind: "quote" | "series" | "fund";
  identifier: string;
  priceType?: string;
}) {
  const api = useApiStatus();
  const enabled = api.status === "ok" && Boolean(identifier);
  const latest = useClientFetch<HeadlineValue>(
    `latest:${kind}:${identifier}:${priceType ?? ""}`,
    async () => {
      if (kind === "series") {
        const row = await fetchSeriesLatest(identifier);
        return {
          date: row.date,
          value: row.value,
          extra: `${row.unit} · ${row.source}`,
          unit: row.unit,
          kind: "series",
        };
      }
      if (kind === "fund") {
        const row = await fetchFundLatest(identifier);
        return {
          date: row.date,
          value: row.price,
          extra: `${row.price_type} · ${row.source}`,
          priceType: row.price_type,
          unit: row.unit,
          kind: "quote",
        };
      }
      const row = await fetchQuoteLatest(identifier, { price_type: priceType || undefined });
      return {
        date: row.date,
        value: row.price,
        extra: `${row.price_type} · ${row.source}`,
        priceType: row.price_type,
        unit: row.unit,
        kind: "quote",
      };
    },
    { enabled },
  );
  const name = useClientFetch(`name:${identifier}`, () => lookupInstrumentName(identifier), {
    enabled,
  });

  if (!identifier || api.status === "unreachable") {
    return null;
  }
  if (latest.status === "loading") {
    return <p className="text-sm text-slate-600">Carregando último valor…</p>;
  }
  if (latest.status === "error") {
    return (
      <p className="text-sm text-red-800">
        {formatApiError(latest.error)}
        {isNotFoundError(latest.error) ? ` — ${copy.common.noSynthetic}.` : null}
      </p>
    );
  }

  return (
    <div className="mt-3">
      {name.status === "success" && name.data && name.data !== identifier ? (
        <p className="text-sm text-slate-700">{name.data}</p>
      ) : null}
      <p className="font-mono text-2xl tabular-nums text-slate-900">
        {formatDisplayValue(latest.data.value, {
          priceType: latest.data.priceType,
          unit: latest.data.unit,
          kind: latest.data.kind,
        })}
      </p>
      <p className="text-xs text-slate-500">
        {latest.data.date} · {latest.data.extra}
      </p>
    </div>
  );
}
