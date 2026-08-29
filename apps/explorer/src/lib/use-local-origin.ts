"use client";

import { useSyncExternalStore } from "react";

import { isLocalPageOrigin } from "@/lib/api";

function subscribe(): () => void {
  return () => {};
}

export function useLocalPageOrigin(): boolean {
  return useSyncExternalStore(subscribe, isLocalPageOrigin, () => false);
}
