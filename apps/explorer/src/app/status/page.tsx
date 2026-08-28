"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { getApiBaseUrl, isLoopbackApiHost } from "@/lib/api";
import { copy } from "@/lib/copy";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

export default function StatusPage() {
  const api = useApiStatus();
  const localOrigin = useLocalPageOrigin();
  const loopbackApi = isLoopbackApiHost();
  const showBase = localOrigin;
  const visitorLoopback = loopbackApi && !localOrigin;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Status da API</h1>
        <p className="mt-1 text-sm text-slate-600">
          Verificação de <code className="font-mono text-xs">GET /v1/health</code>. Este
          explorador não lê PostgreSQL no navegador.
        </p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Saúde</h2>
        {api.status === "loading" ? (
          <p className="mt-2 text-sm text-slate-600">{copy.header.statusChecking}</p>
        ) : null}
        {api.status === "ok" ? (
          <p className="mt-2 text-sm text-teal-800">{copy.header.statusOk}</p>
        ) : null}
        {api.status === "unreachable" ? (
          <p className="mt-2 text-sm text-slate-600">{copy.header.statusDown}</p>
        ) : null}
        <p className="mt-3">
          <button
            type="button"
            onClick={() => api.retry()}
            disabled={api.status === "loading"}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {copy.common.retry}
          </button>
        </p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Origem da API</h2>
        {showBase ? (
          <p className="mt-2 font-mono text-sm text-slate-800">{getApiBaseUrl()}/v1</p>
        ) : visitorLoopback ? (
          <p className="mt-2 text-sm text-slate-700">{copy.api.publicUnavailable}</p>
        ) : (
          <p className="mt-2 text-sm text-slate-700">
            Explorador configurado para a API pública /v1. A origem exata não é exibida para
            visitantes.
          </p>
        )}
      </section>
    </div>
  );
}
