"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type SearchQueryValue = {
  query: string;
  setQuery: (value: string) => void;
};

const SearchQueryContext = createContext<SearchQueryValue>({
  query: "",
  setQuery: () => {},
});

export function SearchQueryProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  const value = useMemo(() => ({ query, setQuery }), [query]);
  return <SearchQueryContext.Provider value={value}>{children}</SearchQueryContext.Provider>;
}

export function useSearchQuery(): SearchQueryValue {
  return useContext(SearchQueryContext);
}
