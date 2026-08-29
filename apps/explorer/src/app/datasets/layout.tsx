import type { Metadata } from "next";

export const metadata: Metadata = { title: "Conjuntos de dados" };

export default function DatasetsLayout({ children }: LayoutProps<"/datasets">) {
  return children;
}
