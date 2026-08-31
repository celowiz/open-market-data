"use client";

import type { ReactNode } from "react";

import { RangeChips, type DateRangeValue, type RangeKey } from "@/components/RangeChips";
import { copy, offlineFormHint } from "@/lib/copy";
import { btnAccent, fieldClass } from "@/lib/ui";
import { useLocalPageOrigin } from "@/lib/use-local-origin";

export type { DateRangeValue, RangeKey };

type DateRangeFormProps = {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onSubmit: (range?: DateRangeValue) => void;
  extra?: ReactNode;
  submitLabel?: string;
  disabled?: boolean;
  disabledHint?: string;
  showShortcuts?: boolean;
  activeRange?: RangeKey;
  onRangeKey?: (key: RangeKey, range: DateRangeValue) => void;
};

export function DateRangeForm({
  start,
  end,
  onStartChange,
  onEndChange,
  onSubmit,
  extra,
  submitLabel = copy.common.loadHistory,
  disabled = false,
  disabledHint,
  showShortcuts = true,
  activeRange,
  onRangeKey,
}: DateRangeFormProps) {
  const localOrigin = useLocalPageOrigin();
  const hint = disabledHint ?? (disabled ? offlineFormHint(localOrigin) : undefined);

  return (
    <form
      className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled) {
          onSubmit();
        }
      }}
    >
      {showShortcuts ? (
        <RangeChips
          value={activeRange}
          disabled={disabled}
          onChange={(key, range) => {
            if (onRangeKey) {
              onRangeKey(key, range);
              return;
            }
            onStartChange(range.start);
            onEndChange(range.end);
            onSubmit(range);
          }}
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="start-date" className="text-sm font-medium text-foreground">
            {copy.common.startDate}
          </label>
          <input
            id="start-date"
            name="start"
            type="date"
            value={start}
            disabled={disabled}
            onChange={(event) => onStartChange(event.target.value)}
            className={fieldClass}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="end-date" className="text-sm font-medium text-foreground">
            {copy.common.endDate}
          </label>
          <input
            id="end-date"
            name="end"
            type="date"
            value={end}
            disabled={disabled}
            onChange={(event) => onEndChange(event.target.value)}
            className={fieldClass}
          />
        </div>
        <div className="contents">{extra}</div>
        <div className="flex items-end">
          <button type="submit" disabled={disabled} className={`w-full ${btnAccent}`}>
            {submitLabel}
          </button>
        </div>
      </div>
      {disabled && hint ? <p className="text-sm text-muted">{hint}</p> : null}
    </form>
  );
}
