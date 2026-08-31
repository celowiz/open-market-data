"use client";

import Link from "next/link";
import type { KeyboardEvent, ReactNode } from "react";

import { DeltaBadge } from "@/components/DeltaBadge";
import { Sparkline } from "@/components/Sparkline";
import type { LatestPrint } from "@/lib/asset";
import { copy } from "@/lib/copy";
import { formatDisplayValue } from "@/lib/format-display-value";
import { formatQuoteSpan, type QuoteSpanFields } from "@/lib/span";
import { cn } from "@/lib/ui";
import { sparklineValues, windowDeltaFromRows, type WindowPoint } from "@/lib/window-delta";

export function AssetRow({
  identifier,
  title,
  href,
  selected = false,
  onSelect,
  latest,
  history,
  loading = false,
  errorText,
  span,
}: {
  identifier: string;
  title?: string;
  href: string;
  selected?: boolean;
  onSelect?: () => void;
  latest?: LatestPrint;
  history?: WindowPoint[];
  loading?: boolean;
  errorText?: string;
  span?: QuoteSpanFields;
}) {
  const points = history ?? [];
  const delta = windowDeltaFromRows(points);
  const spark = sparklineValues(points);
  const spanLabel = span ? formatQuoteSpan(span) : null;
  const interactive = Boolean(onSelect);

  const body = (
    <>
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm text-foreground">{identifier}</p>
          {title && title !== identifier ? (
            <p className="truncate text-xs text-muted">{title}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {spark.length > 1 ? <Sparkline values={spark} className="text-accent" /> : null}
          <div className="text-right">
            {loading ? (
              <div className="flex flex-col items-end gap-1">
                <div className="skeleton h-5 w-16 rounded" />
                <div className="skeleton h-3 w-10 rounded" />
              </div>
            ) : latest ? (
              <>
                <p className="font-mono text-sm tabular-nums text-foreground">
                  {formatDisplayValue(latest.value, {
                    priceType: latest.priceType,
                    unit: latest.unit,
                    kind: latest.kind,
                  })}
                </p>
                {delta ? <DeltaBadge delta={delta} /> : null}
              </>
            ) : errorText ? (
              <p className="max-w-[10rem] truncate font-mono text-[11px] text-danger" title={errorText}>
                {errorText}
              </p>
            ) : (
              <p className="font-mono text-sm text-muted">—</p>
            )}
          </div>
        </div>
      </div>
      {spanLabel ? <p className="mt-1 truncate font-mono text-[11px] text-muted">{spanLabel}</p> : null}
    </>
  );

  const className = cn(
    "block w-full rounded-xl px-3 py-2.5 text-left transition-colors",
    selected ? "bg-elevated ring-1 ring-accent/40" : "hover:bg-elevated/80",
  );

  if (interactive) {
    return (
      <div className={className}>
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={selected}
          aria-current={selected ? "true" : undefined}
          className="w-full text-left"
        >
          {body}
        </button>
        <Link href={href} className="mt-1 inline-block text-[11px] font-medium text-muted hover:text-accent">
          {copy.common.openHistory}
        </Link>
      </div>
    );
  }

  return (
    <Link href={href} className={className}>
      {body}
    </Link>
  );
}

export function AssetRowList({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const items = [...event.currentTarget.querySelectorAll<HTMLElement>("button, a")];
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      items[Math.min(index + 1, items.length - 1)]?.focus();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      items[Math.max(index - 1, 0)]?.focus();
    }
  }

  return (
    <ul aria-label={label} className="flex flex-col gap-0.5" onKeyDown={onKeyDown}>
      {children}
    </ul>
  );
}
