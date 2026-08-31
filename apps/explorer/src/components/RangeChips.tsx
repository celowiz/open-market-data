"use client";

import { copy } from "@/lib/copy";
import { addUtcMonths, addUtcYears, defaultHistoryRange, todayIso } from "@/lib/dates";
import { cn } from "@/lib/ui";

export type DateRangeValue = {
  start: string;
  end: string;
};

export type RangeKey = "1M" | "1A" | "5A" | "max";

export function rangeFromKey(key: RangeKey): DateRangeValue {
  const today = todayIso();
  if (key === "1M") {
    return { start: addUtcMonths(today, -1), end: today };
  }
  if (key === "1A") {
    return { start: addUtcYears(today, -1), end: today };
  }
  if (key === "5A") {
    return { start: defaultHistoryRange(5).start, end: today };
  }
  return { start: "", end: today };
}

export function RangeChips({
  value,
  onChange,
  disabled = false,
}: {
  value?: RangeKey;
  onChange: (key: RangeKey, range: DateRangeValue) => void;
  disabled?: boolean;
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
            onClick={() => onChange(option.key, rangeFromKey(option.key))}
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
