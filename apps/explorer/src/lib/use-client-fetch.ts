"use client";

import { useEffect, useState } from "react";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: unknown };

export function useClientFetch<T>(
  key: string,
  factory: () => Promise<T>,
  options?: { enabled?: boolean },
): LoadState<T> {
  const enabled = options?.enabled ?? true;
  const [tick, setTick] = useState<{ key: string; state: LoadState<T> }>({
    key,
    state: { status: "loading" },
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let cancelled = false;
    factory().then(
      (data) => {
        if (!cancelled) {
          setTick({ key, state: { status: "success", data } });
        }
      },
      (error: unknown) => {
        if (!cancelled) {
          setTick({ key, state: { status: "error", error } });
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // factory is identified by `key` so callers can pass an inline lambda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  if (!enabled || tick.key !== key) {
    return { status: "loading" };
  }
  return tick.state;
}
