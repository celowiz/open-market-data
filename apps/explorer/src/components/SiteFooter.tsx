export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-600">
        <p>
          This Data Explorer only reads the public FastAPI <code className="font-mono">/v1</code>{" "}
          API. It never connects to PostgreSQL, never invents missing prices, and does not offer
          B3 or Yahoo bulk downloads.
        </p>
      </div>
    </footer>
  );
}
