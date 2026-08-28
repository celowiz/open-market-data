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
    <div className="mx-auto max-w-6xl px-4 py-16">
      <div role="alert">
        <h1 className="text-2xl font-semibold text-slate-900">Algo deu errado</h1>
        <p className="mt-2 text-slate-600">{message}</p>
      </div>
      <p className="mt-4">
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
        >
          {copy.common.retry}
        </button>
      </p>
    </div>
  );
}
