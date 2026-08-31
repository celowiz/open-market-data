import { copy } from "@/lib/copy";
import { formatApiError } from "@/lib/api";

export function ErrorBanner({ error, label }: { error: unknown; label?: string }) {
  return (
    <div className="rounded-2xl border border-down/40 bg-down/10 px-4 py-3 text-sm text-danger">
      <p className="font-medium">
        {label ? `${label} · ${copy.api.errorHeading}` : copy.api.errorHeading}
      </p>
      <p className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-foreground/90 sm:text-sm">
        {formatApiError(error)}
      </p>
    </div>
  );
}
