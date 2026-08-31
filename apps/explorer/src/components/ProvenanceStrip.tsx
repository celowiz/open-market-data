import type { ReactNode } from "react";

type ProvenanceItem = {
  source?: string;
  price_type?: string;
  official?: boolean;
  revision?: number;
  raw_artifact_sha256?: string | null;
  retrieved_at?: string | null;
  unit?: string | null;
  currency?: string | null;
};

function unique(values: Array<string | undefined | null>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value && value.trim())))];
}

export function ProvenanceStrip({
  items,
  extra,
}: {
  items: ProvenanceItem[];
  extra?: ReactNode;
}) {
  const sources = unique(items.map((item) => item.source));
  const priceTypes = unique(items.map((item) => item.price_type));
  const units = unique(items.map((item) => item.unit));
  const currencies = unique(items.map((item) => item.currency));
  const officialFlags = [...new Set(items.map((item) => item.official).filter((v) => v !== undefined))];
  const revisions = items.map((item) => item.revision).filter((v): v is number => v !== undefined);
  const sha = items.find((item) => item.raw_artifact_sha256)?.raw_artifact_sha256 ?? null;
  const retrieved = items.find((item) => item.retrieved_at)?.retrieved_at ?? null;

  const officialLabel =
    officialFlags.length === 0
      ? "n/d"
      : officialFlags.length === 1
        ? officialFlags[0]
          ? "sim"
          : "não"
        : "misto";

  const revisionLabel =
    revisions.length === 0
      ? "n/d"
      : `${Math.min(...revisions)}${revisions.length > 1 ? `–${Math.max(...revisions)}` : ""}`;

  return (
    <section
      aria-label="Proveniência"
      className="rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-foreground"
    >
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Proveniência</h2>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-xs text-muted">Fonte</dt>
          <dd>{sources.join(", ") || "n/d"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Tipo de preço</dt>
          <dd className="font-mono">{priceTypes.join(", ") || "n/d"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Oficial</dt>
          <dd>{officialLabel}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Revisão</dt>
          <dd>{revisionLabel}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Unidade / moeda</dt>
          <dd>{[...units, ...currencies].join(" · ") || "n/d"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Recuperado em</dt>
          <dd className="break-all font-mono text-xs">{retrieved ?? "n/d"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted">SHA-256 do artefato bruto</dt>
          <dd className="break-all font-mono text-xs" title={sha ?? undefined}>
            {sha ?? "n/d"}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted">
        Os valores são exibidos exatamente como a API pública os devolve. Respostas vazias ou 404
        não são preenchidas com preços inventados. Os eixos do gráfico usam Number() só para
        plotagem.
      </p>
      {extra}
    </section>
  );
}
