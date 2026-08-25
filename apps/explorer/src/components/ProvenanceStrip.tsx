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
      ? "n/a"
      : officialFlags.length === 1
        ? officialFlags[0]
          ? "yes"
          : "no"
        : "mixed";

  const revisionLabel =
    revisions.length === 0
      ? "n/a"
      : `${Math.min(...revisions)}${revisions.length > 1 ? `–${Math.max(...revisions)}` : ""}`;

  return (
    <section
      aria-label="Provenance"
      className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
    >
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Provenance
      </h2>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-xs text-slate-500">Source</dt>
          <dd>{sources.join(", ") || "n/a"}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Price type</dt>
          <dd className="font-mono">{priceTypes.join(", ") || "n/a"}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Official</dt>
          <dd>{officialLabel}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Revision</dt>
          <dd>{revisionLabel}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Unit / currency</dt>
          <dd>
            {[...units, ...currencies].join(" · ") || "n/a"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Retrieved at</dt>
          <dd className="break-all font-mono text-xs">{retrieved ?? "n/a"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-slate-500">Raw artifact SHA-256</dt>
          <dd className="break-all font-mono text-xs" title={sha ?? undefined}>
            {sha ?? "n/a"}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Values are shown exactly as returned by the public API. Empty or 404 responses are not
        filled with placeholder prices. Chart axes parse decimal strings with Number() for plotting
        only.
      </p>
      {extra}
    </section>
  );
}
