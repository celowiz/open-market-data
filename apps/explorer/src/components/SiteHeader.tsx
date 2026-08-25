"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { getApiBaseUrl } from "@/lib/api";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/sources", label: "Sources" },
  { href: "/datasets", label: "Datasets" },
  { href: "/coverage", label: "Coverage" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const apiBase = getApiBaseUrl();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link href="/" className="text-lg font-semibold tracking-tight text-slate-900">
            Open Market Data
          </Link>
          <p className="text-sm text-slate-600">
            Read-only explorer for{" "}
            <code className="rounded bg-slate-100 px-1 font-mono text-xs">{apiBase}/v1</code>
          </p>
        </div>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {NAV.map((item) => {
            const current =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={`rounded-md px-3 py-2 text-sm font-medium ${
                  current
                    ? "bg-teal-700 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
