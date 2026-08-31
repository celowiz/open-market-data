import type { CoverageItemResponse, CoverageResponse } from "@/lib/types";

function reasonBars(counts: Record<string, number>): Array<{ name: string; count: number }> {
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

function assetClassBars(
  rows: CoverageItemResponse[],
): Array<{ name: string; priced: number; missing: number }> {
  const byClass = new Map<string, { priced: number; missing: number }>();
  for (const row of rows) {
    const current = byClass.get(row.asset_class) ?? { priced: 0, missing: 0 };
    if (row.status === "PRICED" && row.price !== null && row.price !== undefined) {
      current.priced += 1;
    } else {
      current.missing += 1;
    }
    byClass.set(row.asset_class, current);
  }
  return [...byClass.entries()].map(([name, counts]) => ({ name, ...counts }));
}

function CountBar({ label, count, max }: { label: string; count: number; max: number }) {
  const width = max > 0 ? Math.max((count / max) * 100, count > 0 ? 2 : 0) : 0;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="truncate text-foreground">{label}</span>
        <span className="font-mono tabular-nums text-muted">{count}</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-elevated">
        <div className="h-full rounded-full bg-accent" style={{ width: `${width}%` }} />
      </div>
    </li>
  );
}

function SplitBar({
  name,
  priced,
  missing,
}: {
  name: string;
  priced: number;
  missing: number;
}) {
  const total = priced + missing;
  const pricedWidth = total > 0 ? (priced / total) * 100 : 0;
  const missingWidth = total > 0 ? (missing / total) * 100 : 0;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="truncate text-foreground">{name}</span>
        <span className="font-mono tabular-nums text-muted">
          {priced}/{total}
        </span>
      </div>
      <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-elevated">
        <div className="h-full bg-accent" style={{ width: `${pricedWidth}%` }} />
        <div className="h-full bg-border" style={{ width: `${missingWidth}%` }} />
      </div>
    </li>
  );
}

export function CoverageChart({
  data,
  rows,
}: {
  data: CoverageResponse;
  rows: CoverageItemResponse[];
}) {
  const reasons = reasonBars(data.missing_reason_counts);
  const classes = assetClassBars(rows);
  const reasonMax = Math.max(...reasons.map((row) => row.count), 0);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-2xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Motivos de ausência (universo)</h2>
        <p className="mt-1 text-xs text-muted">
          Contagens do relatório completo, não só da página carregada.
        </p>
        {reasons.length === 0 ? (
          <p className="mt-4 text-sm text-muted">Nenhum motivo de ausência neste universo.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-3">
            {reasons.map((row) => (
              <CountBar key={row.name} label={row.name} count={row.count} max={reasonMax} />
            ))}
          </ul>
        )}
      </section>
      <section className="rounded-2xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Priced vs ausente por classe</h2>
        <p className="mt-1 text-xs text-muted">
          Calculado nas linhas já carregadas ({rows.length} de {data.universe_size}).
        </p>
        {classes.length === 0 ? (
          <p className="mt-4 text-sm text-muted">Nenhuma linha carregada ainda.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-3">
            {classes.map((row) => (
              <SplitBar key={row.name} name={row.name} priced={row.priced} missing={row.missing} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
