import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  return { title: { absolute: `${decodeURIComponent(code)} · Open Market Data` } };
}

export default function SeriesDetailLayout({ children }: LayoutProps<"/series/[code]">) {
  return children;
}
