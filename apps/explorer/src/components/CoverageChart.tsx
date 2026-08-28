"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

export function CoverageChart({
  data,
  rows,
}: {
  data: CoverageResponse;
  rows: CoverageItemResponse[];
}) {
  const reasons = reasonBars(data.missing_reason_counts);
  const classes = assetClassBars(rows);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Motivos de ausência (universo)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Contagens do relatório completo, não só da página carregada.
        </p>
        {reasons.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">Nenhum motivo de ausência neste universo.</p>
        ) : (
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reasons} margin={{ top: 8, right: 8, left: 0, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
                <Tooltip />
                <Bar dataKey="count" name="Quantidade" fill="#0f766e" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Priced vs ausente por classe</h2>
        <p className="mt-1 text-xs text-slate-500">
          Calculado nas linhas já carregadas ({rows.length} de {data.universe_size}).
        </p>
        {classes.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">Nenhuma linha carregada ainda.</p>
        ) : (
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={classes} margin={{ top: 8, right: 8, left: 0, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
                <Tooltip />
                <Bar dataKey="priced" name="Com preço" fill="#0f766e" isAnimationActive={false} />
                <Bar dataKey="missing" name="Ausente" fill="#94a3b8" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
    </div>
  );
}
