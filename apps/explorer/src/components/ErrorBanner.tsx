import { formatApiError } from "@/lib/api";

export function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      <p className="font-medium">API error</p>
      <p className="mt-1 whitespace-pre-wrap break-words font-mono text-xs sm:text-sm">
        {formatApiError(error)}
      </p>
    </div>
  );
}
