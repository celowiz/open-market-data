"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { InstrumentSearch } from "@/components/InstrumentSearch";
import { getApiBaseUrl } from "@/lib/api";
import { copy, offlineBannerMessage } from "@/lib/copy";
import { cn } from "@/lib/ui";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

const NAV = [
  { href: "/", label: copy.nav.home },
  { href: "/ativos", label: copy.nav.instruments },
  { href: "/series", label: copy.nav.series },
  { href: "/compare", label: copy.nav.compare },
  { href: "/sources", label: copy.nav.sources },
  { href: "/datasets", label: copy.nav.datasets },
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

  const bannerMessage =
    api.status === "unreachable" ? offlineBannerMessage(revealBase, getApiBaseUrl()) : null;

  return (
    <header className="sticky top-0 z-30 border-b border-border/80 bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center justify-between gap-3">
            <div>
              <Link href="/" className="text-lg font-semibold tracking-tight text-foreground">
                {copy.productName}
              </Link>
              <p className="text-xs text-muted">
                {revealBase ? (
                  <>
                    {copy.header.subtitleLocal}{" "}
                    <code className="rounded bg-elevated px-1 font-mono text-[11px]">
                      {getApiBaseUrl()}/v1
                    </code>
                  </>
                ) : (
                  copy.header.subtitlePublic
                )}
              </p>
            </div>
            <Link
              href="/status"
              aria-current={pathname === "/status" ? "page" : undefined}
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium lg:hidden",
                api.status === "ok"
                  ? "border-up/40 text-up"
                  : api.status === "unreachable"
                    ? "border-down/40 text-down"
                    : "border-border text-muted",
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  api.status === "ok"
                    ? "bg-up"
                    : api.status === "unreachable"
                      ? "bg-down"
                      : "bg-muted",
                )}
                aria-hidden="true"
              />
              {statusLabel}
            </Link>
          </div>
          <div className="flex flex-col gap-2 lg:flex-1 lg:flex-row lg:items-center lg:justify-end lg:gap-4">
            <nav
              aria-label={copy.nav.main}
              className="-mx-1 flex gap-1 overflow-x-auto px-1 lg:justify-end"
            >
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
                    className={cn(
                      "shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                      current
                        ? "bg-accent text-accent-fg"
                        : "text-muted hover:bg-elevated hover:text-foreground",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <Link
              href="/status"
              aria-current={pathname === "/status" ? "page" : undefined}
              className={cn(
                "hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium lg:inline-flex",
                api.status === "ok"
                  ? "border-up/40 text-up"
                  : api.status === "unreachable"
                    ? "border-down/40 text-down"
                    : "border-border text-muted",
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  api.status === "ok"
                    ? "bg-up"
                    : api.status === "unreachable"
                      ? "bg-down"
                      : "bg-muted",
                )}
                aria-hidden="true"
              />
              {statusLabel}
            </Link>
          </div>
        </div>
        <InstrumentSearch variant="compact" />
      </div>
      {bannerMessage ? (
        <div role="alert" className="border-t border-down/30 bg-down/10">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-foreground">{bannerMessage}</p>
            <button
              type="button"
              onClick={() => api.retry()}
              className="w-fit rounded-xl border border-down/40 bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:bg-elevated"
            >
              {copy.common.retry}
            </button>
          </div>
        </div>
      ) : null}
    </header>
  );
}
