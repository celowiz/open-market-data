import type { Metadata } from "next";

export const metadata: Metadata = { title: "Cobertura" };

export default function CoverageLayout({ children }: LayoutProps<"/coverage">) {
  return children;
}
