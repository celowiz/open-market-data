import Link from "next/link";

import { copy } from "@/lib/copy";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-border/80">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-3xl">{copy.footer}</p>
        <Link href="/coverage" className="shrink-0 font-medium text-muted hover:text-accent">
          {copy.nav.coverage}
        </Link>
      </div>
    </footer>
  );
}
