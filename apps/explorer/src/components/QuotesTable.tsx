import type { QuoteResponse } from "@/lib/types";

export function QuotesTable({ quotes }: { quotes: QuoteResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Quote history</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Date
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Price
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Currency
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Price type
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Source
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Official
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Revision
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Unit
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Artifact SHA-256
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
              <td className="px-3 py-2">{quote.official ? "yes" : "no"}</td>
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
