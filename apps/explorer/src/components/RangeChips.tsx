"use client";

import { copy } from "@/lib/copy";
import { rangeFromKey, type DateRangeValue, type RangeKey } from "@/lib/dates";
import type { QuoteSpanFields } from "@/lib/span";
import { cn } from "@/lib/ui";

export type { DateRangeValue, RangeKey };

export function RangeChips({
  value,
  onChange,
  disabled = false,
  span,
}: {
  value?: RangeKey;
  onChange: (key: RangeKey, range: DateRangeValue) => void;
  disabled?: boolean;
  span?: QuoteSpanFields | null;
}) {
  const options: Array<{ key: RangeKey; label: string }> = [
    { key: "1M", label: copy.shortcuts.oneMonth },
    { key: "1A", label: copy.shortcuts.oneYear },
    { key: "5A", label: copy.shortcuts.fiveYears },
    { key: "max", label: copy.shortcuts.max },
  ];

  return (
    <div role="group" aria-label={copy.shortcuts.range} className="flex flex-wrap gap-1">
      {options.map((option) => {
        const selected = value === option.key;
        return (
          <button
            key={option.key}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            onClick={() => onChange(option.key, rangeFromKey(option.key, span))}
            className={cn(
              "inline-flex min-h-11 min-w-11 items-center justify-center rounded-full px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50",
              selected
                ? "bg-accent text-accent-fg"
                : "text-muted hover:bg-elevated hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
