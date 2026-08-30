import type { Metadata } from "next";

export const metadata: Metadata = { title: "Ativos" };

export default function InstrumentsLayout({ children }: LayoutProps<"/instruments">) {
  return children;
}
