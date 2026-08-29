import type { QuoteResponse } from "@/lib/types";

export function QuotesTable({ quotes }: { quotes: QuoteResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Histórico de cotações</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Data
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Preço
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Moeda
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Tipo de preço
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Fonte
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Oficial
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Revisão
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Unidade
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              SHA-256 do artefato
            </th>
          </tr>
        </thead>
        <tbody>
          {quotes.map((quote, index) => (
            <tr key={`${quote.date}-${quote.price_type}-${quote.revision}-${index}`} className="border-t border-slate-100">
              <td className="whitespace-nowrap px-3 py-2 font-mono">{quote.date}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums">{quote.price}</td>
              <td className="px-3 py-2">{quote.currency ?? "—"}</td>
              <td className="px-3 py-2 font-mono">{quote.price_type}</td>
              <td className="px-3 py-2">{quote.source}</td>
              <td className="px-3 py-2">{quote.official ? "sim" : "não"}</td>
              <td className="px-3 py-2">{quote.revision}</td>
              <td className="px-3 py-2">{quote.unit ?? "—"}</td>
              <td className="max-w-[12rem] truncate px-3 py-2 font-mono text-xs" title={quote.raw_artifact_sha256 ?? undefined}>
                {quote.raw_artifact_sha256 ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
