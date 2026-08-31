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
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:py-8">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Status da API</h1>
        <p className="mt-1 text-sm text-muted">
          Verificação de <code className="font-mono text-xs">GET /v1/health</code>. Este
          explorador não lê PostgreSQL no navegador.
        </p>
      </header>

      <section className="rounded-2xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Saúde</h2>
        {api.status === "loading" ? (
          <p className="mt-2 text-sm text-muted">{copy.header.statusChecking}</p>
        ) : null}
        {api.status === "ok" ? (
          <p className="mt-2 text-sm text-accent">{copy.header.statusOk}</p>
        ) : null}
        {api.status === "unreachable" ? (
          <p className="mt-2 text-sm text-muted">{copy.header.statusDown}</p>
        ) : null}
        <p className="mt-3">
          <button
            type="button"
            onClick={() => api.retry()}
            disabled={api.status === "loading"}
            className="rounded-xl border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:bg-elevated disabled:cursor-not-allowed disabled:opacity-60"
          >
            {copy.common.retry}
          </button>
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Origem da API</h2>
        {showBase ? (
          <p className="mt-2 font-mono text-sm text-foreground">{getApiBaseUrl()}/v1</p>
        ) : visitorLoopback ? (
          <p className="mt-2 text-sm text-foreground">{copy.api.publicUnavailable}</p>
        ) : (
          <p className="mt-2 text-sm text-foreground">
            Explorador configurado para a API pública /v1. A origem exata não é exibida para
            visitantes.
          </p>
        )}
      </section>
    </div>
  );
}
