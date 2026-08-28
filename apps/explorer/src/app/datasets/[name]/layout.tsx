import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ name: string }>;
}): Promise<Metadata> {
  const { name } = await params;
  return { title: decodeURIComponent(name) };
}

export default function DatasetDetailLayout({ children }: LayoutProps<"/datasets/[name]">) {
  return children;
}
