"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { fetchHealth } from "@/lib/api";
import { copy } from "@/lib/copy";

export type ApiStatusValue = {
  status: "loading" | "ok" | "unreachable";
  error?: unknown;
  retry: () => void;
};

const ApiStatusContext = createContext<ApiStatusValue>({
  status: "loading",
  retry: () => {},
});

export function ApiStatusProvider({ children }: { children: ReactNode }) {
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<ApiStatusValue["status"]>("loading");
  const [error, setError] = useState<unknown>(undefined);

  const retry = useCallback(() => {
    setStatus("loading");
    setError(undefined);
    setAttempt((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal).then(
      (data) => {
        if (data.status === "ok") {
          setStatus("ok");
          setError(undefined);
          return;
        }
        setStatus("unreachable");
        setError(new Error(copy.api.healthNotOk));
      },
      (err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("unreachable");
        setError(err);
      },
    );
    return () => controller.abort();
  }, [attempt]);

  const value = useMemo<ApiStatusValue>(
    () => ({ status, error, retry }),
    [status, error, retry],
  );
  return <ApiStatusContext.Provider value={value}>{children}</ApiStatusContext.Provider>;
}

export function useApiStatus(): ApiStatusValue {
  return useContext(ApiStatusContext);
}
