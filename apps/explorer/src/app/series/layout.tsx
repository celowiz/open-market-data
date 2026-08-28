import type { Metadata } from "next";

export const metadata: Metadata = { title: "Séries" };

export default function SeriesLayout({ children }: LayoutProps<"/series">) {
  return children;
}
