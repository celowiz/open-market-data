import type { Metadata } from "next";

export const metadata: Metadata = { title: "Fontes" };

export default function SourcesLayout({ children }: LayoutProps<"/sources">) {
  return children;
}
