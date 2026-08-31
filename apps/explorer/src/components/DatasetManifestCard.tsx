"use client";

import Link from "next/link";

import { isBlockedDatasetDownload } from "@/lib/links";
import type { DatasetListing } from "@/lib/types";

export function DatasetManifestCard({
  dataset,
  detailHref,
}: {
  dataset: DatasetListing;
  detailHref?: string;
}) {
  const blocked = isBlockedDatasetDownload(dataset.sources, dataset.dataset_name);
  const fileUrl = !blocked && dataset.url ? dataset.url : null;

  return (
    <article className="rounded-2xl border border-border bg-surface p-4">
      <h2 className="text-lg font-semibold text-foreground">
        {detailHref ? (
          <Link href={detailHref} className="text-accent hover:underline">
            {dataset.dataset_name}
          </Link>
        ) : (
          dataset.dataset_name
        )}
      </h2>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted">Schema</dt>
          <dd className="font-mono">{dataset.schema_version}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Data do snapshot</dt>
          <dd className="font-mono">{dataset.snapshot_date}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Gerado em</dt>
          <dd className="font-mono text-xs">{dataset.generated_at}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Linhas</dt>
          <dd>{dataset.row_count}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Licença</dt>
          <dd>{dataset.license}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Redistribuição</dt>
          <dd className="font-mono text-xs">{dataset.redistribution_policy}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted">Fontes</dt>
          <dd>{dataset.sources.join(", ") || "—"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted">Chave do objeto</dt>
          <dd className="break-all font-mono text-xs">{dataset.object_key}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted">SHA-256</dt>
          <dd className="break-all font-mono text-xs">{dataset.sha256}</dd>
        </div>
      </dl>
      <div className="mt-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Atribuição</h3>
        {dataset.attribution.length === 0 ? (
          <p className="text-sm text-muted">Nenhuma linha de atribuição neste manifesto.</p>
        ) : (
          <ul className="mt-1 list-disc pl-5 text-sm text-foreground">
            {dataset.attribution.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
      </div>
      {fileUrl ? (
        <p className="mt-3 text-sm">
          <a
            href={fileUrl}
            rel="nofollow noopener noreferrer"
            target="_blank"
            className="font-medium text-accent hover:underline"
          >
            Arquivo do conjunto
          </a>
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted">
          {blocked
            ? "Nenhum download é oferecido para fontes bloqueadas (incluindo B3 e Yahoo)."
            : "Nenhuma URL pública de arquivo está configurada para este manifesto."}
        </p>
      )}
    </article>
  );
}
