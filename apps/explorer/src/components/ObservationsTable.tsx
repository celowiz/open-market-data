import type { SeriesObservationResponse } from "@/lib/types";

export function ObservationsTable({
  observations,
}: {
  observations: SeriesObservationResponse[];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Series observations</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Date
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Value
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Unit
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Source
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Revision
            </th>
          </tr>
        </thead>
        <tbody>
          {observations.map((row, index) => (
            <tr key={`${row.date}-${row.revision}-${index}`} className="border-t border-slate-100">
              <td className="whitespace-nowrap px-3 py-2 font-mono">{row.date}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums">{row.value}</td>
              <td className="px-3 py-2">{row.unit}</td>
              <td className="px-3 py-2">{row.source}</td>
              <td className="px-3 py-2">{row.revision}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
