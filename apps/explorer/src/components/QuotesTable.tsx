import { formatDisplayValue } from "@/lib/format-display-value";
import type { QuoteResponse } from "@/lib/types";
import { tableWrapClass, tdClass, thClass, trClass } from "@/lib/ui";

export function QuotesTable({ quotes }: { quotes: QuoteResponse[] }) {
  return (
    <div className={tableWrapClass}>
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Histórico de cotações</caption>
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className={thClass}>
              Data
            </th>
            <th scope="col" className={thClass}>
              Preço
            </th>
            <th scope="col" className={thClass}>
              Moeda
            </th>
            <th scope="col" className={thClass}>
              Tipo de preço
            </th>
            <th scope="col" className={thClass}>
              Fonte
            </th>
            <th scope="col" className={thClass}>
              Oficial
            </th>
            <th scope="col" className={thClass}>
              Revisão
            </th>
            <th scope="col" className={thClass}>
              Unidade
            </th>
            <th scope="col" className={thClass}>
              SHA-256 do artefato
            </th>
          </tr>
        </thead>
        <tbody>
          {quotes.map((quote, index) => (
            <tr key={`${quote.date}-${quote.price_type}-${quote.revision}-${index}`} className={trClass}>
              <td className={`whitespace-nowrap font-mono ${tdClass}`}>{quote.date}</td>
              <td className={`whitespace-nowrap font-mono tabular-nums ${tdClass}`}>
                {formatDisplayValue(quote.price, { priceType: quote.price_type, unit: quote.unit })}
              </td>
              <td className={tdClass}>{quote.currency ?? "—"}</td>
              <td className={`font-mono ${tdClass}`}>{quote.price_type}</td>
              <td className={tdClass}>{quote.source}</td>
              <td className={tdClass}>{quote.official ? "sim" : "não"}</td>
              <td className={tdClass}>{quote.revision}</td>
              <td className={tdClass}>{quote.unit ?? "—"}</td>
              <td className={`max-w-[12rem] truncate font-mono text-xs ${tdClass}`} title={quote.raw_artifact_sha256 ?? undefined}>
                {quote.raw_artifact_sha256 ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
