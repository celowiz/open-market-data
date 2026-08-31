"use client";

import { formatApiError, getApiBaseUrl, isNetworkFailure } from "@/lib/api";
import { copy } from "@/lib/copy";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const local = useLocalPageOrigin();
  const message = isNetworkFailure(error)
    ? local
      ? copy.api.localUnreachable(getApiBaseUrl())
      : copy.api.publicUnavailable
    : formatApiError(error);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-16">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Algo deu errado</h1>
        <p className="mt-2 text-muted">{message}</p>
      </div>
      <p className="mt-4">
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:brightness-110"
        >
          {copy.common.retry}
        </button>
      </p>
    </div>
  );
}
