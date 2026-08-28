import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const { identifier } = await params;
  return { title: decodeURIComponent(identifier) };
}

export default function QuoteLayout({ children }: LayoutProps<"/quotes/[identifier]">) {
  return children;
}
