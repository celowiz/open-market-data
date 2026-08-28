"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchHealth } from "@/lib/api";

export type ApiStatusValue =
  | { status: "loading" }
  | { status: "ok" }
  | { status: "unreachable"; error: unknown };

const ApiStatusContext = createContext<ApiStatusValue>({ status: "loading" });

export function ApiStatusProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<ApiStatusValue>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal).then(
      (data) => {
        if (data.status === "ok") {
          setValue({ status: "ok" });
          return;
        }
        setValue({
          status: "unreachable",
          error: new Error("Health check failed"),
        });
      },
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setValue({ status: "unreachable", error });
      },
    );
    return () => controller.abort();
  }, []);

  const memo = useMemo(() => value, [value]);
  return <ApiStatusContext.Provider value={memo}>{children}</ApiStatusContext.Provider>;
}

export function useApiStatus(): ApiStatusValue {
  return useContext(ApiStatusContext);
}
