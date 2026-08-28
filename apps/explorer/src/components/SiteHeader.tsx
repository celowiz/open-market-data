"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { InstrumentSearch } from "@/components/InstrumentSearch";
import { formatApiError, getApiBaseUrl } from "@/lib/api";
import { copy } from "@/lib/copy";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

const NAV = [
  { href: "/", label: copy.nav.home },
  { href: "/series", label: copy.nav.series },
  { href: "/compare", label: copy.nav.compare },
  { href: "/sources", label: copy.nav.sources },
  { href: "/datasets", label: copy.nav.datasets },
  { href: "/coverage", label: copy.nav.coverage },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const api = useApiStatus();
  const revealBase = useLocalPageOrigin();

  const statusLabel =
    api.status === "ok"
      ? copy.header.statusOk
      : api.status === "unreachable"
        ? copy.header.statusDown
        : copy.header.statusChecking;
  const statusClass =
    api.status === "ok"
      ? "border-teal-200 bg-teal-50 text-teal-900"
      : api.status === "unreachable"
        ? "border-red-200 bg-red-50 text-red-800"
        : "border-slate-200 bg-slate-50 text-slate-700";

  const bannerMessage =
    api.status === "unreachable"
      ? revealBase
        ? formatApiError(api.error)
        : copy.api.publicBanner
      : null;

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Link href="/" className="text-lg font-semibold tracking-tight text-slate-900">
              {copy.productName}
            </Link>
            <p className="text-sm text-slate-600">
              {revealBase ? (
                <>
                  {copy.header.subtitleLocal}{" "}
                  <code className="rounded bg-slate-100 px-1 font-mono text-xs">
                    {getApiBaseUrl()}/v1
                  </code>
                </>
              ) : (
                copy.header.subtitlePublic
              )}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
            <Link
              href="/status"
              aria-current={pathname === "/status" ? "page" : undefined}
              className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-medium ${statusClass}`}
            >
              {statusLabel}
            </Link>
            <nav aria-label={copy.nav.main} className="flex flex-wrap gap-1">
              {NAV.map((item) => {
                const current =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={current ? "page" : undefined}
                    className={`rounded-md px-3 py-2 text-sm font-medium ${
                      current ? "bg-teal-700 text-white" : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
        <InstrumentSearch variant="compact" />
      </div>
      {bannerMessage ? (
        <div role="alert" className="border-t border-amber-200 bg-amber-50">
          <p className="mx-auto max-w-6xl px-4 py-3 text-sm text-amber-950">{bannerMessage}</p>
        </div>
      ) : null}
    </header>
  );
}
