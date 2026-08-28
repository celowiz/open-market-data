import type { Metadata } from "next";

export const metadata: Metadata = { title: "Comparar" };

export default function CompareLayout({ children }: LayoutProps<"/compare">) {
  return children;
}
