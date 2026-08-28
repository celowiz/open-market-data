"use client";

import { useCallback, useEffect, useState } from "react";

type HistoryPagesState<TPage, TItem> = {
  key: string;
  status: "loading" | "success" | "error";
  error: unknown;
  items: TItem[];
  firstPage: TPage | null;
  nextCursor: string | null;
  loadingMore: boolean;
};

export function useHistoryPages<TPage, TItem>(options: {
  key: string;
  enabled: boolean;
  fetchPage: (cursor: string | undefined, signal?: AbortSignal) => Promise<TPage>;
  itemsOf: (page: TPage) => TItem[];
  cursorOf: (page: TPage) => string | null | undefined;
}): {
  status: "loading" | "success" | "error";
  error: unknown;
  items: TItem[];
  firstPage: TPage | null;
  hasMore: boolean;
  loadingMore: boolean;
  loadMore: () => void;
} {
  const { key, enabled, fetchPage, itemsOf, cursorOf } = options;
  const [tick, setTick] = useState<HistoryPagesState<TPage, TItem>>({
    key,
    status: "loading",
    error: null,
    items: [],
    firstPage: null,
    nextCursor: null,
    loadingMore: false,
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const controller = new AbortController();
    fetchPage(undefined, controller.signal).then(
      (page) => {
        if (controller.signal.aborted) {
          return;
        }
        setTick({
          key,
          status: "success",
          error: null,
          items: itemsOf(page),
          firstPage: page,
          nextCursor: cursorOf(page) ?? null,
          loadingMore: false,
        });
      },
      (error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setTick({
          key,
          status: "error",
          error,
          items: [],
          firstPage: null,
          nextCursor: null,
          loadingMore: false,
        });
      },
    );
    return () => controller.abort();
    // Identified by `key`; fetchPage/itemsOf/cursorOf are recreated each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  const loadMore = useCallback(() => {
    if (!enabled || tick.key !== key || tick.loadingMore || !tick.nextCursor) {
      return;
    }
    const cursor = tick.nextCursor;
    setTick((current) =>
      current.key !== key || current.nextCursor !== cursor
        ? current
        : { ...current, loadingMore: true },
    );
    fetchPage(cursor).then(
      (page) => {
        setTick((prev) => {
          if (prev.key !== key || prev.nextCursor !== cursor) {
            return prev;
          }
          return {
            ...prev,
            items: [...prev.items, ...itemsOf(page)],
            nextCursor: cursorOf(page) ?? null,
            loadingMore: false,
          };
        });
      },
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setTick((prev) => ({ ...prev, loadingMore: false, error }));
      },
    );
  }, [cursorOf, enabled, fetchPage, itemsOf, key, tick.key, tick.loadingMore, tick.nextCursor]);

  if (!enabled || tick.key !== key) {
    return {
      status: "loading",
      error: null,
      items: [],
      firstPage: null,
      hasMore: false,
      loadingMore: false,
      loadMore,
    };
  }

  return {
    status: tick.status,
    error: tick.error,
    items: tick.items,
    firstPage: tick.firstPage,
    hasMore: Boolean(tick.nextCursor),
    loadingMore: tick.loadingMore,
    loadMore,
  };
}
