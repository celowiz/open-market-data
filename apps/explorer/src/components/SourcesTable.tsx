import type { SourceResponse } from "@/lib/types";
import { tableWrapClass, tdClass, thClass, trClass } from "@/lib/ui";

export function SourcesTable({ sources }: { sources: SourceResponse[] }) {
  return (
    <div className={tableWrapClass}>
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Fontes de dados públicas</caption>
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className={thClass}>
              Nome
            </th>
            <th scope="col" className={thClass}>
              Nome de exibição
            </th>
            <th scope="col" className={thClass}>
              Oficial
            </th>
            <th scope="col" className={thClass}>
              Redistribuição
            </th>
            <th scope="col" className={thClass}>
              Ingestão
            </th>
            <th scope="col" className={thClass}>
              API pública
            </th>
            <th scope="col" className={thClass}>
              Conjunto público
            </th>
            <th scope="col" className={thClass}>
              Licença
            </th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.name} className={trClass}>
              <td className={`font-mono ${tdClass}`}>{source.name}</td>
              <td className={tdClass}>{source.display_name}</td>
              <td className={tdClass}>{source.official ? "sim" : "não"}</td>
              <td className={`font-mono text-xs ${tdClass}`}>{source.redistribution_policy}</td>
              <td className={tdClass}>{source.ingestion_enabled ? "sim" : "não"}</td>
              <td className={tdClass}>{source.public_api_enabled ? "sim" : "não"}</td>
              <td className={tdClass}>{source.public_dataset_enabled ? "sim" : "não"}</td>
              <td className={tdClass}>{source.data_license ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
