import type { SourceResponse } from "@/lib/types";

export function SourcesTable({ sources }: { sources: SourceResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Fontes de dados públicas</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Nome
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Nome de exibição
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Oficial
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Redistribuição
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Ingestão
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              API pública
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Conjunto público
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Licença
            </th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.name} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono">{source.name}</td>
              <td className="px-3 py-2">{source.display_name}</td>
              <td className="px-3 py-2">{source.official ? "sim" : "não"}</td>
              <td className="px-3 py-2 font-mono text-xs">{source.redistribution_policy}</td>
              <td className="px-3 py-2">{source.ingestion_enabled ? "sim" : "não"}</td>
              <td className="px-3 py-2">{source.public_api_enabled ? "sim" : "não"}</td>
              <td className="px-3 py-2">{source.public_dataset_enabled ? "sim" : "não"}</td>
              <td className="px-3 py-2">{source.data_license ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
