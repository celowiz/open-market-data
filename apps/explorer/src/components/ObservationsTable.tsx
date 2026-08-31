import { formatDisplayValue } from "@/lib/format-display-value";
import type { SeriesObservationResponse } from "@/lib/types";
import { tableWrapClass, tdClass, thClass, trClass } from "@/lib/ui";

export function ObservationsTable({
  observations,
}: {
  observations: SeriesObservationResponse[];
}) {
  return (
    <div className={tableWrapClass}>
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Observações da série</caption>
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className={thClass}>
              Data
            </th>
            <th scope="col" className={thClass}>
              Valor
            </th>
            <th scope="col" className={thClass}>
              Unidade
            </th>
            <th scope="col" className={thClass}>
              Fonte
            </th>
            <th scope="col" className={thClass}>
              Revisão
            </th>
          </tr>
        </thead>
        <tbody>
          {observations.map((row, index) => (
            <tr key={`${row.date}-${row.revision}-${index}`} className={trClass}>
              <td className={`whitespace-nowrap font-mono ${tdClass}`}>{row.date}</td>
              <td className={`whitespace-nowrap font-mono tabular-nums ${tdClass}`}>
                {formatDisplayValue(row.value, { kind: "series", unit: row.unit })}
              </td>
              <td className={tdClass}>{row.unit}</td>
              <td className={tdClass}>{row.source}</td>
              <td className={tdClass}>{row.revision}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
