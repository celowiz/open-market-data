import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "Ativos" };

export default function AtivosLayout({ children }: { children: ReactNode }) {
  return children;
}
