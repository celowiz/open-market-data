"use client";

import Link from "next/link";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ExampleCards } from "@/components/ExampleCards";
import { InstrumentSearch } from "@/components/InstrumentSearch";
import { EmptyState, LoadingState } from "@/components/Status";
import { SourcesTable } from "@/components/SourcesTable";
import { fetchSources } from "@/lib/api";
import { useClientFetch } from "@/lib/use-client-fetch";

export default function HomePage() {
  const sources = useClientFetch("sources", () => fetchSources());

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-8">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Public market data explorer
        </h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Browse quotes, series, funds, coverage, and published dataset manifests from the local
          FastAPI. This app does not talk to PostgreSQL, CVM, or B3 directly.
        </p>
      </section>

      <InstrumentSearch />

      <section aria-labelledby="examples-heading" className="flex flex-col gap-3">
        <h2 id="examples-heading" className="text-xl font-semibold text-slate-900">
          Example identifiers
        </h2>
        <p className="text-sm text-slate-600">
          Each card calls the live API. A 404 shows the API error body — never a made-up price.
        </p>
        <ExampleCards />
      </section>

      <section aria-labelledby="sources-heading" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="sources-heading" className="text-xl font-semibold text-slate-900">
            Public sources
          </h2>
          <Link href="/sources" className="text-sm font-medium text-teal-800 hover:underline">
            Full sources table
          </Link>
        </div>
        <p className="text-sm text-slate-600">
          From <code className="font-mono text-xs">GET /v1/sources</code>. Sources with
          public API enabled appear here, including Yahoo.
        </p>
        {sources.status === "loading" ? <LoadingState label="Loading sources…" /> : null}
        {sources.status === "error" ? <ErrorBanner error={sources.error} /> : null}
        {sources.status === "success" && sources.data.length === 0 ? (
          <EmptyState>
            <p>No public sources are visible yet.</p>
            <p className="mt-2">
              Seed providers, run <code className="font-mono text-xs">marketdata backfill</code>,
              and start uvicorn on <code className="font-mono text-xs">127.0.0.1:8000</code>.
            </p>
          </EmptyState>
        ) : null}
        {sources.status === "success" && sources.data.length > 0 ? (
          <SourcesTable sources={sources.data} />
        ) : null}
      </section>

      <section aria-labelledby="datasets-heading" className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 id="datasets-heading" className="text-xl font-semibold text-slate-900">
          Datasets
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Public Parquet manifests (ODbL / attribution) live on the{" "}
          <Link href="/datasets" className="font-medium text-teal-800 hover:underline">
            datasets
          </Link>{" "}
          page. B3 files are not offered for download.
        </p>
      </section>
    </div>
  );
}
