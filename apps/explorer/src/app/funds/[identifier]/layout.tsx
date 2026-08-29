import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const { identifier } = await params;
  return { title: decodeURIComponent(identifier) };
}

export default function FundLayout({ children }: LayoutProps<"/funds/[identifier]">) {
  return children;
}
